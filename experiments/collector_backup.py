import subprocess, os, traceback
import argparse
from dataclasses import dataclass
from typing import Optional

#result-no-rag-200
#result-full-200
#result-bm25-200

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Collect experimental results')
parser.add_argument('-s', '--suggestion', action='store_true', 
                    help='Consider suggestions (default: False, use -s to enable)')
parser.add_argument('-m', '--method', type=str, default='bm25',
                    help='Method name (e.g., bm25, full, no-rag)')
args = parser.parse_args()

logs = f'/data2/user/experimental-results'
if not args.suggestion:
    logs += '-no-suggestion'
logs += f'/{args.method}'

hammer_only_ground_truth_cases = []

ans = 0
cnt = 0
bad = 0
only_hammer = []
no_llm = False
unsolved = []
nprompts = {}
giveup = 0
total_num_tokens = 0

rerun = []
notrun = [(0, x) for x in range(160)] + [(1, x) for x in range(40)]
benchmarks = notrun

@dataclass
class BenchmarkResult:
    split: int
    data_id: int
    hammer_only: bool = False
    num_tokens: int = 0
    solved: bool = False
    weird_error: Optional[str] = None 

    def __str__(self):
        return f'{self.split},{self.data_id}'

    def __hash__(self):
        return hash((self.split, self.data_id))

    def __eq__(self, other):
        return self.split == other.split and self.data_id == other.data_id

def check_solved(result_path: str) -> bool:
    if os.path.exists(result_path):
        with open(result_path, 'r') as f:
            content = f.read()
        if content == 'None':
            return False
        else:
            return True
    else:
        return False

def check_no_llm(log_path: str) -> bool:
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()
        if content.find('Start Querying LLM') != -1:
            return False
        else:
            return True
    else:
        return False

def parse_num_tokens(prompt_root: str) -> int:
    num_tokens = 0
    for f in os.listdir(prompt_root):
        if f.startswith('result'):
            content = open(os.path.join(prompt_root, f), 'r').read()
            cpos = content.find('[Completion Tokens] ')
            num_tokens += int(content[cpos + 20:].strip())
    return num_tokens

weird_error_patterns = [
    ("Chat Query Error", "OpenAI API Error"),
    ("No current goal", "No Proof Goal error")
]

traceback_patterns = [
    ("could not be acquired", "Lock Error"),
    ("Pfile is invalid", "Proof File Error"),
    ("Server quit", "Server Quit Error"),
    ("Server timeout", "Server Timeout Error"),
]

def parse_weird_error(
    log_path: str,
    result_path: str
) -> Optional[str]:
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()

        for pattern in weird_error_patterns:
            if pattern[0] in content:
                return pattern[1]

        if content.find('Traceback (most recent call last):') != -1:
            traceback = content[content.find(
                'Traceback (most recent call last):'
            ):]
            for pattern in traceback_patterns:
                if pattern[0] in traceback:
                    return pattern[1]
            return "Other Error, Manual Check Needed"
        elif not os.path.exists(result_path):
            return "Result file does not exist"
        else:
            return None
    else:
        return "Log file does not exist"
    

def parse_benchmark_result(
    split: int,
    data_id: int,
    data_root: str,
    prompt_root: str,
    result_path: str,
    log_path: str
) -> BenchmarkResult:
    solved = check_solved(result_path)
    hammer_only = check_no_llm(log_path)
    num_tokens = parse_num_tokens(prompt_root)
    weird_error = parse_weird_error(log_path)
    return BenchmarkResult(
        split, data_id, no_llm, num_tokens, solved, weird_error
    )

for folder in os.listdir(logs):
    if not folder.startswith('logfiles_'):
        continue
    num = int(folder[folder.rfind('_')+1:])
    sp = int(folder[folder.find('_')+1:folder.rfind('_')])
    abspath = os.path.join(logs, folder)
    result_loc = os.path.join(abspath, 'results.v')
    runtime_log = os.path.join(abspath, 'runtime.log')
    prompt_root = os.path.join(abspath, 'prompts')
    notrun.remove((sp, num))
    cnt = cnt + 1

    result = parse_benchmark_result(
        sp, num, logs, prompt_root, result_loc, runtime_log
    )


    cnt = cnt + 1

    if os.path.exists(result_loc):
        with open(result_loc, 'r') as f:
            content = f.read()
        if content == 'None':
            unsolved += [(sp, num)]
        else:
            ans = ans + 1
    else:
        unsolved += [(sp, num)]

    if os.path.exists(runtime_log):
        log = open(runtime_log).read()
        if log.find('Start Querying LLM') != -1:
            no_llm = False
        else:
            no_llm = True
        if no_llm:
            only_hammer += [(sp, num)]
    


    if os.path.exists(runtime_log):
        log = open(runtime_log).read()
        if log.find('Chat Query Error') != -1:
            rerun += [(sp, num)]
            bad += 1
            print('openai', sp, num)
            continue
        if False and log.find('Goal=\nNo current goal') != -1:
            rerun += [(sp, num)]
            bad += 1
            print('No Goal Error', sp, num)
            continue
        if log.find('Traceback (most recent call last):') != -1:
            error_info = log[log.find('Traceback ('):]
            if "Exception during query_llm" in error_info:
                print('query_llm error', sp, num)
                rerun += [(sp, num)]
                bad += 1
                continue
            elif 'openai.' in error_info:
                print('openai', sp, num)
                rerun += [(sp, num)]
                bad += 1
                continue
            elif error_info.find('could not be acquired') != -1:
                print('lock', sp, num)
                rerun += [(sp, num)]
                bad += 1
                continue
            elif error_info.find('Pfile is invalid') != -1:
#               print('Pfile Error:', sp, num)
                #rerun += [(sp, num)]
                bad += 1
                continue
            elif error_info.find('Server quit') != -1:
                print('Server quit:', sp, num)
                #rerun += [(sp, num)]
                unsolved += [(sp, num)]
                bad += 1
                continue
            elif error_info.find('Server timeout') != -1:
                print('Server timeout:', sp, num)
                #rerun += [(sp, num)]
                unsolved += [(sp, num)]
                bad += 1
                continue
            else:
                print('Other', sp, num)
                rerun += [(sp, num)]
                unsolved += [(sp, num)]
                bad += 1
                continue 
            pass
    else:
        rerun += [(sp, num)]
        continue
    cnt = cnt + 1
    if not os.path.exists(result_loc):
        print('no result', sp, num)
        rerun += [(sp, num)]
        continue
    if os.path.exists(result_loc) and os.path.exists(runtime_log):
        content = open(result_loc).read()
        log = open(runtime_log).read()
        if log.find('Start Querying LLM') != -1:
            #print(folder)
            no_llm = False
        else:
            no_llm = True
        if content == 'None':
            if log.find('Starting Round: 26') == -1:
                print('weird', sp, num)
            unsolved += [(sp, num)]
        else:
            ans = ans + 1

        if content.find('rewrite !') != -1:
            #print('rewrite ! in', sp, num)
            pass
        
        pfolder = os.path.join(logs, folder, 'prompts')
        files = os.listdir(pfolder)


        #print(folder, num_prompts)

        if no_llm:
            only_hammer += [(sp, num)]
            nprompts[str((sp, num))] = 0
            continue

        nprompts[str((sp, num))] = num_tokens
        total_num_tokens += num_tokens
    else:
        unsolved += [(sp, num)]
#        print(f'catch error at {folder}')

from operator import itemgetter
print(f'solved: {ans}/{cnt + bad}')
print(f'unsolved:', sorted(unsolved, key=itemgetter(0, 1)))
print(f'only hammer:', len(only_hammer), sorted(only_hammer))
print(f'$total:', total_num_tokens * 4.4/1e6)
for j in unsolved:
    if str(j) in nprompts:
        total_num_tokens -= nprompts[str(j)]
        del nprompts[str(j)]
print(f'$total solved:', total_num_tokens / ans)
print(f'num tokens:', nprompts)
print('bad:', bad)
print('rerun:', rerun + notrun)

result_summary = {
    "solved": ans,
    "unsolved": sorted(unsolved, key=itemgetter(0, 1)),
    "only_hammer": sorted(only_hammer, key=itemgetter(0, 1)),
    "total_cost": total_num_tokens * 4.4 / 1e6,
    "avg_cost": total_num_tokens / ans if ans > 0 else 0,
    "num_tokens": nprompts,
    "bad_cases": bad,
    "rerun_cases": rerun,
}

output_name = "summary-" + args.method
if args.suggestion:
    output_name += "-with-suggestion"

with open(f'experiments/{output_name}.json', 'w') as f:
    import json
    json.dump(result_summary, f)