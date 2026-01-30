import os

os.environ['PROMPT_ROOT'] = os.path.join(os.getcwd(), 'prompt')

from argparse import ArgumentParser
from settings import run_test, run_benchmark
from env import _1h, _2gb, set_env, cache_root, _16gb


parser = ArgumentParser(description='LLM-based prover for Coq')
parser.add_argument('-i', '--index', type=int, default=-1)
parser.add_argument('-r', '--run_test', action='store_true')
parser.add_argument('-t', '--time_limit', type=int, default=_1h)
parser.add_argument('-m', '--memory_limit', type=int, default=_2gb)
parser.add_argument('-s', '--split', type=int, default=-1)
parser.add_argument('-c', '--config', type=str, default='configs/default.json')
parser.add_argument('-o', '--output-dir', type=str, 
                    default=cache_root+'/logs/logfiles')
parser.add_argument('-p', '--pass-id', type=str, 
                    default='')
exec_cfg = vars(parser.parse_args())

os.environ['output_dir'] = exec_cfg['output_dir']
print(os.environ['output_dir'])

if exec_cfg.get('run_test', True):
    set_env(_1h, _2gb * 1024, 20)
    run_test('configs/conf-test.json')
else:
    sp = exec_cfg.get('split', -1)
    id = exec_cfg.get('index', -1)
    tl = exec_cfg.get('time_limit', _1h)
    ml = exec_cfg.get('memory_limit', _16gb)
    set_env(tl, ml * 1024, 20, pass_no=exec_cfg['pass_id'])
    run_benchmark(sp, id, exec_cfg['config'])