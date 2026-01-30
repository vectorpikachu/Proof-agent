import sys, os
from proof.localctx import LocalContext, LspResponseError
from env import _1h, _16gb, get_output_dir
from coqpyt.coq.proof_file import ProofFile
from agent.solve import solve
from typing import Optional
from logging import getLogger
import rag.bm25 as bm25
logger = getLogger('Prover')

def get_repo(name: Optional[str]):
    if name in ['compcert', 'ext-lib', 'fourcolor', 'math-classes',
                'reglang', 'buchberger', 'hoare-tut', 'zorns-lemma',
                'huffman', 'poltac', 'dblib', 'zfc']:
        return 'test-repos'
    if name in ['sudoku', 'bertrand', 'graph-theory', 'stalmarck',
                'qarith-stern-brocot', 'coqeal']:
        return 'val-repos'
    if name in ['bb5', 'pnvrocqlib']:
        return 'cutoff-repos'
    if name == 'my_single_test':
        return 'my_tests'
    if name is None:
        return None

def transfer_file(file: str, short_space: Optional[str]) -> str:
    if file.find('.opam') != -1:
        return '/home/syc/' + file[file.find('.opam'):]
    if short_space is None:
        return file
    if file.find(short_space) != -1:
        short_file = file[file.find(short_space):]
    else:
        short_file = file
    return os.path.join(
        '/home/syc/CoqStoq_backup',
        get_repo(short_space), short_file
    )

def run(lctx: LocalContext) -> str | None:
    logger.info(f'Starting Prover')
    os.environ['COMMENT'] = str(lctx.use_docstring)
    logger.info(f'Use Comment: {os.environ["COMMENT"]}')

    logger.info('Initializing Pfenv...')
    lctx.init_pfenv()
    logger.info('Pfenv Initialized')
    logger.info(f'workspace={lctx.penv_dup.workspace}')
    logger.info(f'steps={lctx.legacy_steps}')
    logger.info('Output Dir: ' + get_output_dir())

    workspace = lctx.workspace
    short_space = None
    if workspace is not None:
        short_space = workspace[workspace.rfind('/')+1:]
    fpath = transfer_file(lctx.penv_dup.fpath, short_space)

    logger.info(f'File Path: {fpath}')
    logger.info(f'pfile.fpath: {lctx.penv_dup.fpath}')
    logger.info(f'pfile.workspace: {lctx.penv_dup.workspace}')

    with ProofFile(lctx.penv_dup.fpath, workspace=lctx.penv_dup.workspace,
                   use_disk_cache=lctx.use_cache,
                   memory_limit=_16gb, timeout=_1h) as pfile:
        if not pfile.is_valid:
            for step in pfile.steps:
                # logger.info(f'Checking Step: {step.text}')
                diags = step.diagnostics
                for diag in diags:
                    if (diag.severity is not None) and diag.severity <= 1:
                        logger.error(f'Invalid Step: {step.text}')
                        logger.error(f'Diag: {diag.message}')
                        assert False, 'Pfile is invalid'
        
        # 把需要证明的命题之前的 legacy text 加载
        pfile.exec(lctx.legacy_steps)
        logger.info('Legacy Loaded')
        ctx_terms = pfile.context.terms
        lctx.visible_paths = {'lib': set(), 'workspace': set()}
        for w in ctx_terms.values():
            path = transfer_file(w.file_path, short_space)
            if path.find('.opam') != -1:
                lctx.visible_paths['lib'].add(path)
            elif ((short_space is not None) 
                  and path.find(short_space) != -1):
                lctx.visible_paths['workspace'].add(path)
        if fpath in lctx.visible_paths['workspace']:
            lctx.visible_paths['workspace'].remove(fpath)
        lctx.visible_paths['all'] = lctx.visible_paths['lib'].union(
            lctx.visible_paths['workspace']
        )

    if lctx.retrieval_method == 'mybm25':
        bm25.init_cluster(
            lctx.visible_paths['workspace'],
            fpath,
            lctx.legacy_steps - lctx.head_steps,
        )

    return solve(lctx, fpath, logger)