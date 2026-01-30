import subprocess, os, traceback
import argparse
from dataclasses import dataclass, asdict, field
from typing import Optional, Tuple, Dict

#result-no-rag-200
#result-full-200
#result-bm25-200

# Parse command-line arguments

ev_modules = ['provability', 'induction', 'destruct']
print(ev_modules)
def get_weight(method: str, module: str) -> float:
    return 1

parser = argparse.ArgumentParser(description='Collect experimental results')
parser.add_argument('-s', '--suffix', type=str, default='',
                    help='Consider suggestions (default: False, use -s to enable)')
parser.add_argument('-m', '--method', type=str, default='bm25',
                    help='Method name (e.g., bm25, full, no-rag)')
parser.add_argument("-i", "--incomplete-results", action="store_true",
                    help='Consider incomplete results (default: False, use -i to enable)')
parser.add_argument("--hide-solved", action="store_true",
                    help='Hide error message from solved benchmarks (default: False, use --hide-solved to enable)')
parser.add_argument("--gpt4-log", action="store_true",
                    help='Use gpt4 log file (default: False, use --gpt4-log to enable)')
parser.add_argument("--cobblestone-bench", action="store_true",
                    help='Use cobblestone benchmark (default: False, use --cobblestone-bench to enable)')


args = parser.parse_args()
if args.gpt4_log:
    logs = '/data2/lhz/experimental-results-gpt4-1106-add-rag/gpt4-1106/'
else:
    logs = f'/data2/lhz/experimental-results'
    if args.suffix:
        logs += f'-{args.suffix}'
    logs += f'/{args.method}'

name = args.method + '-' + args.suffix

@dataclass
class BenchmarkResult:
    split: int
    data_id: int
    hammer_only: bool = False
    num_tokens: float = 0
    solved: bool = False
    weird_error: Optional[str] = None
    ev_num_tokens: Dict[str, int] = field(default_factory=dict)

    def __str__(self):
        return f'{self.split},{self.data_id}'

    def __hash__(self):
        return hash((self.split, self.data_id))

    def __eq__(self, other):
        return self.split == other.split and self.data_id == other.data_id
    
    def to_dict(self):
        """Convert the dataclass to a dictionary for JSON serialization."""
        return asdict(self)

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
        return 'Start Querying LLM' not in content
    else:
        return False


import tiktoken
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Counts the number of tokens in a string for a specific model.
    """
    try:
        # Get the encoding specifically for the model (e.g., gpt-4, gpt-3.5-turbo)
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to the standard encoding for modern models if model not found
        encoding = tiktoken.get_encoding("cl100k_base")
        
    # Encode the text into integer tokens
    token_integers = encoding.encode(text)
    
    # Return the length of the list
    return len(token_integers)

def parse_num_tokens(prompt_root: str) -> Tuple[float, Dict[str, int]]:
    num_tokens = 0
    ev_tokens = {module: 0 for module in ev_modules}
    for f in os.listdir(prompt_root):
        if f.startswith('result') or (f.find('emb') != -1):                
            content = open(os.path.join(prompt_root, f), 'r').read()
            if f.find('emb') != -1:
                token = count_tokens(content[:content.find('[Tools]')], 'gpt-4') + 1082
                inp_token = 0
            else:
                cpos = content.find('[Input Tokens] ')
                inp_token = int(content[cpos + 15:content.find('\n', cpos)].strip())
                cpos = content.find('[Completion Tokens] ')
                #print(prompt_root, f)
                #print(content[cpos + 20:].strip())
                token = int(content[cpos + 20:content.find('\n', cpos)].strip())
            ev = False
            for module in ev_modules:
                if module in f:
                    ev_tokens[module] += token + inp_token
                    ev = True
                    break
            
            if not ev: num_tokens += token + inp_token
    return num_tokens, ev_tokens

weird_error_patterns = [
    ("Chat Query Error", "OpenAI API Error"),
    ("No current goal", "No Proof Goal error")
]

traceback_patterns = [
    ("could not be acquired", "Lock Error"),
    ("Pfile is invalid", "Proof File Error"),
    ("Server quit", "Server Quit Error"),
    ("Server timeout", "Server Timeout Error"),
    ("Exception during query_llm", "LLM Error"),
    ("openai.", "OpenAI API Error"),
]

weird_error_antipatterns = [
    ("Starting Round: 26", "Not Finished Benchmark"),
]

def detect_http_error(content: str) -> Optional[str]:
    pos = 0
    while True:
        http_50_pos = content.find("HTTP/1.1 50", pos)
        if http_50_pos == -1:
            return None
        
        llm_success_pos = content.find("LLM API Call Succeeded", http_50_pos)
        if llm_success_pos == -1:
            return "HTTP Error"
        
        pos = http_50_pos + 1

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
        
        http_error = detect_http_error(content)
        if http_error is not None:
            return http_error

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
            if 'returning ftext' in content:
                return None
            for pattern in weird_error_antipatterns:
                if not (pattern[0] in content):
                    return pattern[1]
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
    #print(data_root)
    if not os.path.exists(data_root):
        return BenchmarkResult(
            split, data_id, False, 0, False, "Benchmark not tested"
        )
    solved = check_solved(result_path)
    hammer_only = check_no_llm(log_path)
    p = len([
        x for x in os.listdir(prompt_root) if (x.find('emb') != -1) or x.startswith('result')
    ])
    if p > 20 and solved:
        print(sp, num, 'too many prompts', p)
        solved = False
    num_tokens, ev_tokens = parse_num_tokens(prompt_root)
    if hammer_only:
        num_tokens = 0
    weird_error = parse_weird_error(log_path, result_path)
    if solved:
        weird_error = None        
    
    return BenchmarkResult(
        split, data_id, hammer_only, num_tokens, solved, weird_error, ev_tokens
    )


from util import benchmarks as _benchmarks
from util import cobblestone_bench as _cobblestone_bench
if args.cobblestone_bench:
    benchmarks = _cobblestone_bench
else:
    benchmarks = _benchmarks

hammer_only_ground_truth_cases = []
ans = 0
only_hammer = []
unsolved = []
sum_tokens = 0
sum_gen_tokens = 0
sum_ev_tokens = 0
results = {}
notrun = 0
rerun = []

for (sp, num) in benchmarks:
    abspath = os.path.join(logs, f'logfiles_{sp}_{num}')
    result_loc = os.path.join(abspath, 'results.v')
    runtime_log = os.path.join(abspath, 'runtime.log')
    prompt_root = os.path.join(abspath, 'prompts')
    
    result = parse_benchmark_result(
        sp, num, abspath, prompt_root, result_loc, runtime_log
    )

    if args.incomplete_results and result.weird_error == "Benchmark not tested":
        #print(sp, num)
        notrun += 1
        rerun += [str((sp, num))]
        continue

    if args.hide_solved and result.solved:
        result.weird_error = None

    results[str((sp, num))] = result.to_dict()

    ev_calls = 0
    if os.path.exists(prompt_root):
        for file in os.listdir(prompt_root):
            if file.startswith('ev'):
                ev_calls += 1
    if ev_calls > 8 and result.solved:
        print(f'ev_calls too large: {sp}, {num}, {ev_calls}')

    if result.solved:
        ans = ans + 1
        if result.hammer_only:
            only_hammer.append(str((sp, num)))
    else:
        unsolved.append(str((sp, num)))
    #print(result.ev_num_tokens)
    cur_ev_tokens = sum([
        result.ev_num_tokens[module_name] * get_weight(name, module_name)
        for module_name in ['provability', 'induction', 'destruct']
    ])
    if result.solved:
        sum_tokens += result.num_tokens + cur_ev_tokens
        sum_gen_tokens += result.num_tokens
        sum_ev_tokens += cur_ev_tokens
    if result.weird_error:
        rerun += [str((sp, num))]
        print(f'weird error: {result.weird_error}, {sp}, {num}')


output_name = "summary-" + args.method
if args.suffix:
    output_name += f"-{args.suffix}"

if args.gpt4_log:
    output_name = 'summary-gpt4-1106'



json_result = {
    "solved": ans,
    "total": len(benchmarks),
    "hammer_only_num": len(only_hammer),
    "total_cost": sum_tokens,
    "num_tokens": sum_gen_tokens,
    "ev_num_tokens": sum_ev_tokens,
    "hammer_only": only_hammer,
    "unsolved": unsolved,
    "detailed_results": results,
    "rerun": rerun
}

with open(f'experiments/{output_name}.json', 'w') as f:
    import json
    json.dump(json_result, f, indent=4)

print('NOTRUN benchmarks:', notrun)
