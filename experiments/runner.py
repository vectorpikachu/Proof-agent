from pathlib import Path
import subprocess, os, traceback
from filelock import FileLock
import argparse
import os, sys
from multiprocessing import Pool
from util import benchmarks, invalid_benchmarks, cobblestone_bench, cobblestone_in_test, random_cobblestone_bench, RERUN_COBBLESTONE_EXP

config_paths = {
    "gpt4-first20": "configs/conf-gpt4.json",
    "bm25": "configs/conf-bm25.json",
    "bm25-nodoc": 'configs/conf-bm25-nodoc.json',
    "norag": 'configs/conf-norag.json',
    "default": "configs/default.json",
    "branch-check-bm25": "configs/conf-branch-check-bm25.json",
    "branch-check-dense": "configs/conf-branch-check-dense.json",
    "branch-check-bm25-nodoc": "configs/conf-branch-check-bm25-nodoc.json",
    "o3-first-bm25": "configs/conf-o3-first-bm25.json",
    "scratch-everytime": "configs/conf-scratch.json",
    "bm25-no-example": "configs/conf-bm25-no-example.json",
    "gpt4-1106": "configs/conf-gpt4-1106.json",
}

hammer_cache_path = {
    "branch-check-bm25": "/data2/user/proof_cache/hammer_cache_p4",
    "branch-check-dense": "/data2/user/proof_cache/hammer_cache_p4",
    "branch-check-bm25-nodoc": "/data2/user/proof_cache/hammer_cache_p4",
}

new_benchmarks = [
    (0, x) for x in range(160, 173) if (0, x) not in invalid_benchmarks
]

todo_benchmarks = {
    "gpt4-first20": benchmarks[:20],
    "bm25": [],
    "bm25-nodoc": [],
    "branch-check-bm25": [],
    "branch-check-dense": [
        (0, 31), (0, 64), (0, 65), (0, 95), (0, 124), (0, 151), (1, 4), (1, 10)
    ],
    "default": [
        (0, 157), (0, 158), (0, 159), (0, 160), (0, 161), (1, 1), (1, 2), (1, 3)
    ],
    "gpt4-1106": RERUN_COBBLESTONE_EXP
}

def get_todo(config_name: str):
    return todo_benchmarks.get(config_name, benchmarks)


def get_cmd(s, i, log_dir, cfg_path):
    return f"""
timeout 300m python3 main.py -s {s} -i {i} -o {log_dir} -c {cfg_path}
"""

def get_exp_root_dir():
    return os.environ.get(
        "EXP_ROOT_DIR", 
        '/data2/user/experimental-results-no-suggestion/'
    )

def execute_with_config(arg, config_name):
    # Guard against malformed benchmark tuples so we get a clearer error
    if not (isinstance(arg, (tuple, list)) and len(arg) == 2):
        raise ValueError(f"Unexpected benchmark item for {config_name}: {arg!r}")
    s, i = arg
    cfg_path = config_paths[config_name]
    work_dir = os.path.join(get_exp_root_dir(), config_name)
    log_dir = os.path.join(work_dir, 'logfiles_' + str(s) + '_' + str(i))
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    cmd = get_cmd(s, i, log_dir, cfg_path)
    with FileLock('experiments/rebuild.lock', timeout=300):
        subprocess.run(
            ['python3', 'dataset_build.py', 
            "-s", str(s), "-i", str(i)],
            cwd='/home/user/PLResearch/CoqStoq',
            capture_output=True,
            check=True,
        )

    print(f'[Start] config={config_name}, s={s}, i={i}', flush=True)
    env = os.environ.copy()
    env["HAMMER_CACHE_DIR"] = hammer_cache_path.get(
        config_name,
        "/data2/user/proof_cache/hammer_cache"
    )
    subprocess.run(cmd, shell=True, env=env)
    print(f'[End] config={config_name}, s={s}, i={i}', flush=True)


def exec_bm25(arg): return execute_with_config(arg, "bm25")
def exec_gpt4_first20(arg): return execute_with_config(arg, "gpt4-first20")
def exec_bm25_nodoc(arg): return execute_with_config(arg, "bm25-nodoc")
def exec_norag(arg): return execute_with_config(arg, "norag")
def exec_default(arg): return execute_with_config(arg, "default")
def exec_branch_check_bm25(arg): 
    return execute_with_config(arg, "branch-check-bm25")
def exec_o3_first_bm25(arg):
    return execute_with_config(arg, "o3-first-bm25")
def exec_branch_check_dense(arg):
    return execute_with_config(arg, "branch-check-dense")
def exec_branch_check_bm25_nodoc(arg):
    return execute_with_config(arg, "branch-check-bm25-nodoc")
def exec_scratch_everytime(arg):
    return execute_with_config(arg, "scratch-everytime")
def exec_bm25_no_example(arg):
    return execute_with_config(arg, "bm25-no-example")

def exec_gpt4_1106(arg):
    return execute_with_config(arg, "gpt4-1106")

"""
exec_bm25((0, 57))
"""

def run(p): return (p[0])(p[1])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run experiments with specified config(s)")
    parser.add_argument(
        "-c", "--config",
        type=str,
        required=True,
        help="Config(s) to use (comma-separated): gpt4-first20, bm25, bm25-nodoc, norag, default, branch-check-bm25, o3-first-bm25, branch-check-dense, branch-check-bm25-nodoc, scratch-everytime, bm25-no-example"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Number of workers in Pool (default: 4)"
    )
    parser.add_argument(
        "-e", "--exp-root-dir",
        type=str,
        default=None,
        help="Experiment root directory (default: None)"
    )
    args = parser.parse_args()

    # Parse comma-separated configs
    config_names = [c.strip() for c in args.config.split(',')]
    
    # Validate all config names
    invalid_configs = [c for c in config_names if c not in config_paths]
    if invalid_configs:
        print(f"Error: Invalid config(s): {', '.join(invalid_configs)}", file=sys.stderr)
        print(f"Valid configs: {', '.join(config_paths.keys())}", file=sys.stderr)
        sys.exit(1)

    if args.exp_root_dir is not None:
        os.environ['EXP_ROOT_DIR'] = args.exp_root_dir
    
    sys.stdout = open(os.path.join(get_exp_root_dir(), 'run.out'), 'w')
    sys.stderr = open(os.path.join(get_exp_root_dir(), 'run.err'), 'w')

    # Map config names to their execution functions
    config_exec_map = {
        "gpt4-first20": exec_gpt4_first20,
        "bm25": exec_bm25,
        "bm25-nodoc": exec_bm25_nodoc,
        "norag": exec_norag,
        "default": exec_default,
        "branch-check-bm25": exec_branch_check_bm25,
        "o3-first-bm25": exec_o3_first_bm25,
        "branch-check-dense": exec_branch_check_dense,
        "branch-check-bm25-nodoc": exec_branch_check_bm25_nodoc,
        "scratch-everytime": exec_scratch_everytime,
        "bm25-no-example": exec_bm25_no_example,
        "gpt4-1106": exec_gpt4_1106,
    }

    # Create tasks for all config + benchmark combinations
    all_tasks = []
    for config_name in config_names:
        exec_func = config_exec_map[config_name]
        benchmarks_for_config = get_todo(config_name)
        all_tasks.extend([(exec_func, benchmark) for benchmark in benchmarks_for_config])
    
    print(f"Running {len(all_tasks)} tasks across {len(config_names)} config(s) with {args.workers} workers", flush=True)

    # Execute all tasks in parallel
    with Pool(args.workers) as p:
        p.map(run, all_tasks)

    os.system(
        f'find /home/user/PLResearch/ -name "coqpyt_aux_*" -type f -delete'
    )
