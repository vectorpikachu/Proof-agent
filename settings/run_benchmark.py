import sys, os
if __name__ == '__main__':
    sys.path[0] = '/home/syc/CoqStoq/agent'

from env import coqstoq_root, get_output_dir, set_env

if __name__ == '__main__':
    set_env(int(sys.argv[3]), int(sys.argv[4]))

import traceback
from logging import getLogger
from coqstoq.eval_thms import Position
from prover import run
from proof.localctx import LocalContext, PathEnv
from coqstoq import get_theorem, Split, get_theorem_list
from restore import FileRestorer
from prompt.util import ModelHub

logger = getLogger('PrepareBenchmark')

def get_pos(content: list[str], spos: Position, epos: Position):
    if spos.line == epos.line:
        return content[spos.line][spos.column:epos.column]
    else:
        fline = content[spos.line][spos.column:]
        mlines = '\n'.join(content[spos.line + 1: epos.line])
        lline = content[epos.line][:epos.column]
        return fline + '\n' + mlines + '\n' + lline

def run_benchmark(sp_cfg: int, idx: int, config_loc: str):
    suf = ''
    if idx == -1:
        logger.error('Index error')
        sys.exit(1)
    match sp_cfg:
        case 1:
            thm = get_theorem(Split.VAL, idx, coqstoq_root)
            suf = 'val'
        case 0:
            thm = get_theorem(Split.TEST, idx, coqstoq_root)
            suf = ''
        case 2:
            thm = get_theorem(Split.CUTOFF, idx, coqstoq_root)
            suf = 'cutoff'
        case 4:
            thm = get_theorem("my_tests", idx, coqstoq_root)
            suf = 'my_tests'
        case _:
            logger.error('Split error')
            sys.exit(1)

    print(f"Running Benchmark for {thm.project.dir_name}", flush=True)
    print(f"Task: {thm.path}", flush=True)

    workspace = os.path.join(coqstoq_root, f"datasets/dataset_{sp_cfg}_{idx}",
                             thm.project.dir_name)
    assert ('_CoqProject' in os.listdir(workspace))
    
    fpath = os.path.join(workspace, thm.path)
    logger.info(f'Task Info=\n{fpath}')
    env_dup = PathEnv(fpath, workspace)
    
    print(fpath, flush=True)

    content = open(fpath, 'r').read().split('\n')
    proved = get_pos(content, Position(0, 0), thm.theorem_start_pos)
    proof = get_pos(content, thm.proof_start_pos, thm.proof_end_pos)
    print(proof, flush=True)
    # 我们还需要保留剩下的 proved text
    # 从 thm.proof_end_pos -> 文件末尾
    proved_cont = get_pos(content, thm.proof_end_pos,
                          Position(len(content) - 1, len(content[-1]) - 1))
    logger.info(f"The following legacy texts are: \n{proved_cont}")
    
    content = get_pos(content, thm.theorem_start_pos, thm.theorem_end_pos)
    
    logger.info(f"Theorem content:\n{content}")

    logger.info("Start Task")
    with FileRestorer() as restorer:
        restorer.backup(fpath)

        lctx = LocalContext(
            penv_dup=env_dup,
            legacy_text=proved,
            content=content,
            legacy_text_cont=proved_cont, # Updated.
            instr=thm.project.compile_args,
            config_loc=config_loc,
        )
        logger.info('LocalContext Prepared')

        try:
            result = run(lctx)
            with open(f'{get_output_dir()}/results.v', 'w') as f:
                f.write(str(result))
            #logger.info(f"End Task with Result:\n{result}")
        except Exception as e:
            trback = traceback.format_exc()
            exc = traceback.format_exception(e)
            excs = '\n'.join(exc)
            logger.error(f'{trback}\n{excs}')
            
        

if __name__ == '__main__':
    run_benchmark(int(sys.argv[1]), int(sys.argv[2]))