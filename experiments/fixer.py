import subprocess, os, traceback

#results-ckpt-2025-04-30_no_history_dependent_rag
#results-2025-05-04-no-cold-start-history-all
logs = '/home/lhz/PLResearch/.cache/logs'
# logs = '/Volumes/Data/CoqProjectPKU/data2/syc/proof_cache/logs/'

ans = 0
cnt = 0
only_hammer = []
no_llm = False
unsolved = []
nprompts = {}
giveup = 0
for folder in os.listdir(logs):
    if not folder.startswith('logfiles_'):
        continue
    num = int(folder[folder.rfind('_')+1:])
    cnt = cnt + 1
    abspath = os.path.join(logs, folder)
    runtime_log = os.path.join(abspath, 'runtime.log')


    content = open(runtime_log, 'r').read()
    if content.find('There is already an Ltac named _my_move_hyp.') != -1:
        if num < 35:
            print(f'Fixing {num}', flush=True)
            subprocess.run(
                ['python3', 'dataset_build.py', str(num)],
                cwd='/home/lhz/PLResearch/CoqStoq',
            )