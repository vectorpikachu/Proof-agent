import os, logging, resource, shutil, sys
from icecream import ic

"CTX Name Config"
ctx_id = 3 # 0: local, 1: server, 2: chuyue server, 3: Hangzhou server

"Prover Info"
verbose = True
cache_root = ['/Volumes/Data/CoqProjectPKU/data2/syc/proof_cache/',
              '/data2/syc/proof_cache/',
              '/home/chuyue/coq/.cache/',
              '/data2/lhz/proof_cache'][ctx_id]

output_dir = ['a', 'b', 'c',
    '/data2/lhz/output'][ctx_id]

# TODO: it is not used currently
new_db_root = '/home/chuyue/coq/database_rebuild'

prover_root = ['/Users/syc/Desktop/coq-agent', 
               '/home/syc/coq-agent',
               '/home/chuyue/coq/coq-agent',
               '/home/lhz/PLResearch/coq-agent'][ctx_id]

prompt_files_loc = f'{prover_root}/prompt/'


num_procs = [4, 64, 20, 64][ctx_id]

"Benchmark Info"
coqstoq_root = ['/Volumes/Data/CoqProjectPKU/CoqStoq/', 
                '/home/syc/CoqStoq/',
                '/home/chuyue/coq/CoqStoq',
                '/home/lhz/PLResearch/CoqStoq'][ctx_id]

_coqstoq_root = ['/Volumes/Data/CoqProjectPKU/_CoqStoq/', 
                 '/data2/syc/CoqStoq/',
                 '/home/chuyue/coq/CoqStoq',
                 '/data2/lhz/CoqStoq'][ctx_id]
bak_coqstoq_root = [
    '/Volumes/Data/CoqProjectPKU/bak_CoqStoq/',
    '/data2/syc/proof_cache/backup/CoqStoq/',
    '/home/chuyue/coq/CoqStoq',
    '/data2/lhz/proof_cache/backup/CoqStoq'
][ctx_id]

"Toy Example Case Info"
tmp_root = f'{cache_root}/.tmp'
example_root = f'{prover_root}/examples'

"Limits"
_1h = 5 * 60 * 60
_16gb = 16 * 1024 * 1024
_80gb = 80 * 1024 * 1024
_2gb = 2 * 1024 * 1024
_30m = 1800

"LLM Configs"
base_url = 'https://llm.xmcp.ltd/'
# base_url='https://api.openai-proxy.org'

# LHZ's API Key
# api_key = 'sk-Rm0q8_1zgRsDpPVnF80wPQ'
# Yican API Key
# api_key = 'sk-Y8NLVx8Zzty-jacFEhQTXw'
# SCW's API Key
api_key = 'sk-Y8NLVx8Zzty-jacFEhQTXw'
# close API Key
# api_key = 'sk-xku0VV3ytXZ1r6pO1KhdUf5cetr00MNVnYunpKn9OohMkud3'
# API KEY without rate limit
# api_key = 'sk-1tEGM4sXRxbLwcrsQ0JPUQ'
aoai_api_key=""
aoai_base_url=""

yunwu_base_url='https://yunwu.ai/v1'
yunwu_api_key= 'sk-LYcuP9BNMcabq42HEWP5JVagLf0OIzbtuYTuGBdwo2z9rsCZ'

qingyun_base_url='https://qyapi.yzqyzl.cn/v1'
qingyun_api_key='sk-slyljJLqH90ggPyKV6fhfQCgjmFXtAnW2bcEBLUif7LiMiGC'
## CLUSTER

def get_output_dir():
    return os.environ['output_dir'].rstrip('/')

def get_prompt_cache_root():
    return os.path.join(
        cache_root,
        'prompt_cache_response',
        os.environ.get('PASS_NO', '')
    )

def set_env(tlimit: int, mlimit: int, loglevel = 15, pass_no = ''):
    os.environ['CACHE_HOME_DIR'] = cache_root
    os.environ['PASS_NO'] = pass_no
    os.system('mkdir -p ' + get_prompt_cache_root())
    os.system('mkdir -p ' + get_prompt_cache_root() + "/streaming")

    output_dir = get_output_dir()
    os.system(f'rm -rf {output_dir}')
    os.makedirs(output_dir)
    os.makedirs(f'{output_dir}/pfiles')
    os.makedirs(f'{output_dir}/cfiles')
    os.makedirs(f'{output_dir}/prompts')
    os.makedirs(f'{output_dir}/hammers')
    os.makedirs(f'{output_dir}/failing-trials')
    os.makedirs(f'{output_dir}/rag-query-results')
    stdout_file = os.path.join(output_dir, 'stdout.log')
    stderr_file = os.path.join(output_dir, 'stderr.log')
    sys.stdout = open(stdout_file, 'w')
    sys.stderr = open(stderr_file, 'w')

    os.system(f'rm -rf {output_dir}/runtime.log')
    logging.basicConfig(
        filename = f'{output_dir}/runtime.log',                 
        level=loglevel,
        format='%(asctime)s::%(levelname)s::%(name)s\n%(filename)s::%(funcName)s.%(lineno)d:\n%(message)s\n\n'
    )

    ic(output_dir)

    # Ensure coq-lsp is on PATH (virtualenv activation may have hidden opam bin)
    def _ensure_coqlsp():
        if shutil.which('coq-lsp'):
            return
        # Try OPAM_SWITCH_PREFIX first
        candidates = []
        prefix = os.environ.get('OPAM_SWITCH_PREFIX')
        if prefix:
            candidates.append(os.path.join(prefix, 'bin'))
        # Fallback scan of ~/.opam switches (lightweight)
        opam_root = os.path.expanduser('~/.opam')
        if os.path.isdir(opam_root):
            try:
                for sw in os.listdir(opam_root):
                    bdir = os.path.join(opam_root, sw, 'bin')
                    if os.path.isfile(os.path.join(bdir, 'coq-lsp')):
                        candidates.append(bdir)
            except Exception:
                pass
        seen = set()
        for bdir in candidates:
            if bdir in seen:
                continue
            seen.add(bdir)
            if os.path.isfile(os.path.join(bdir, 'coq-lsp')):
                os.environ['PATH'] = bdir + ':' + os.environ.get('PATH', '')
                logging.getLogger('env').info(f'Auto-added coq-lsp path: {bdir}')
                break
        if not shutil.which('coq-lsp'):
            logging.getLogger('env').warning('coq-lsp still not found after PATH augmentation.')
    _ensure_coqlsp()
    


    #print(mlimit)
    resource.setrlimit(resource.RLIMIT_CPU, (tlimit, tlimit))
    #resource.setrlimit(resource.RLIMIT_DATA, (mlimit, mlimit))

def get_prompt_files_loc():
    print(os.environ.get('PROMPT_ROOT', "not found"))
    return os.environ.get('PROMPT_ROOT', prompt_files_loc)