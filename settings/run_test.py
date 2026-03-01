import sys, os, traceback
from prover import run
from examples.testenv import reset_test_env
from env import tmp_root
from proof.localctx import LocalContext, parse, PathEnv
from logging import getLogger
from prompt.util import ModelHub

logger = getLogger('PrepareTest')

def run_test(config_loc: str):
    texts = reset_test_env()
    path = f'{tmp_root}/readme.v'
    path_dup = path[:-2] + '_.v'

    os.system(f'cp {path} {path_dup}')
    #print(path, path_dup)
    # TODO: The LocalContext usage seems not being updated here.
    lctx = LocalContext(
        penv_dup=PathEnv(path_dup, None),
        legacy_text=open(path).read()[:55],
        content=open(path).read()[55:],
        instr=[],
        config_loc=config_loc
    )
    try:
        result = run(lctx)
        logger.info(f"End Task with Result:\n{result}")
    except Exception as e:
        trback = traceback.format_exc()
        exc = traceback.format_exception(e)
        excs = '\n'.join(exc)
        logger.error(f'{trback}\n{excs}')
