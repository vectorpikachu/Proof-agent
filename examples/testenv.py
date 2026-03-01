import os
from env import example_root, cache_root, tmp_root
from coqpyt.coq.base_file import CoqFile


def reset_test_env():
    os.environ['CACHE_HOME_DIR'] = cache_root
    if os.path.exists(tmp_root):
        os.system(f'rm -rf {tmp_root}')
    os.system(f'mkdir {tmp_root}')
    os.system(f'cp {example_root}/readme.v.bak {tmp_root}/readme.v')
    os.system(f'cp {example_root}/readme_add.v.bak {tmp_root}/readme_add.v')
    os.system(f'cp {example_root}/deadproof.v {tmp_root}/deadproof.v')

    with CoqFile(f'{tmp_root}/readme.v') as cfile:
        texts = [step.text for step in cfile.steps]
    return texts
