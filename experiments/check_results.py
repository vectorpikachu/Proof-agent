from util import cobblestone_bench, random_cobblestone_bench
import os

logs = f'/data2/lhz/experimental-results-gpt4-1106-add-rag/gpt4-1106'

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
    
benchmarks = cobblestone_bench
num_success = 0

for (sp, num) in benchmarks:
    abspath = os.path.join(logs, f'logfiles_{sp}_{num}')
    result_loc = os.path.join(abspath, 'results.v')
    runtime_log = os.path.join(abspath, 'runtime.log')
    prompt_root = os.path.join(abspath, 'prompts')
    success = check_solved(result_loc)
    print(f'Split: {sp}, Num: {num}, Solved: {success}')
    if success:
        num_success += 1
    
print(f"Total items: {len(benchmarks)}")
print(f"Successful items: {num_success}")
print(f"Success rate: {num_success / len(benchmarks):.2%}")
