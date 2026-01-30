import shutil
import subprocess, hashlib, pickle, os, traceback, sys, json
from coqpyt.coq.structs import Step
from coqpyt.coq.base_file import CoqFile, ResponseError
from typing import List, Dict, Optional, Tuple
from proof.term import _term_type, may_intro
from env import _1h, cache_root, _2gb, get_output_dir, num_procs, _16gb
from logging import getLogger
from prompt.util import ModelHub
from configs.params import HyperParams
import sys
from icecream import ic
import tempfile
import os
from pathlib import Path

def get_expr(step: Step) -> Optional[List]:
    """
    Since we are Coq.8.18, expr is always a list.
    """
    if (
        step.ast.span is not None
        and isinstance(step.ast.span, dict)
        and "v" in step.ast.span
        and isinstance(step.ast.span["v"], dict)
        and "expr" in step.ast.span["v"]
    ):
        return step.ast.span["v"]["expr"]
    return None

logger = getLogger('LocalContextInternal')
hammer_cache_dir_loc = os.environ.get('HAMMER_CACHE_DIR', f'{cache_root}/hammer_cache_p3')

class LspResponseError(Exception):
    def __init__(self, err_info: str):
        super().__init__(err_info)
        self.err_info = err_info

    def __str__(self):
        return self.err_info


def fetch_hammer_result():
    hamlog_path = f'{get_output_dir()}/hamlog'
    hamerr_path = f'{get_output_dir()}/hamerr'
    
    # If hamlog doesn't exist or is empty, and hamerr exists, there was an error
    if not os.path.exists(hamlog_path) or os.path.getsize(hamlog_path) == 0:
        if os.path.exists(hamerr_path):
            err = open(hamerr_path, 'r').read()
            if err.strip():
                # Return the error content instead of raising exception
                # This will be handled by the caller
                return err.strip()
        return None
    
    out = open(hamlog_path, 'r').read()
    err = open(hamerr_path, 'r').read() if os.path.exists(hamerr_path) else ""
    
    if (err.find('Hammer failed') != -1):
        return None
    
    out = out + '\n'
    if out.find('Replace the hammer tactic with') != -1:
        pos = out.find('Replace the hammer tactic with:') + 31
        out = out[pos:].lstrip()
        out = out[:out.find('\n')]
        out = out.lstrip().rstrip()
        if not (out.endswith('.')):
            out += '.'
        return ' ' + out + ' '
    else: return None

class EStep:
    def __init__(self, step: Step, my_idx: int, thm_idx: int, 
                 last_bullet_idx: int, nblock_idx: int,
                 stpos: int):
        self.step = step
        self.my_idx = my_idx
        self.thm_idx = thm_idx
        self.lb_idx = last_bullet_idx
        self.nblock_idx = nblock_idx
        self.stpos = stpos

    @property
    def text(self):
        return self.step.text

    @property
    def expr(self):
        return get_expr(self.step)
    
    def __repr__(self):
        return f'\n[EStep]\t\n[Text]\t\n{self.text.lstrip().rstrip()}\t\nmy_idx: {self.my_idx}\t\nthm_idx: {self.thm_idx}\t\nlast_bullet_idx: {self.lb_idx}\t\nnblock_idx: {self.nblock_idx})\t\npos:{self.stpos}\n\n'
    

class PathEnv:
    def __init__(self, fpath: str, workspace: Optional[str]):
        self.fpath = fpath
        self.workspace = workspace    

    def __repr__(self):
        return f'PathEnv(fpath: {self.fpath}\nworkspace: {self.workspace})'

class ParseError(Exception):
    def __init__(self, text: str):
        super().__init__('Error: Error when Parsing Coq Response')
        self.text = text

    def __str__(self):
        return self.text

EXTERNAL_SAFE = f"""

From Hammer Require Import Hammer.
Set Hammer GSMode {num_procs}.
Set Hammer ATPLimit 50.
Set Hammer ReconstrLimit 50.

"""

TOOLS = """

From Depinfo Require Import Loader.
Ltac _my_move_hyp := repeat match goal with | [H: _ |- _] => revert H end.

"""

class LocalContext:
    def __init__(self, penv_dup: PathEnv,
                 legacy_text: str, content: str,
                 legacy_text_cont: str,
                 instr: list[str],
                 config_loc: str):

        self.penv_dup     = penv_dup
        self.content      = content
        self.workspace    = penv_dup.workspace
        self.visible_paths = {}
        self.head_steps    = 0
        self.compile_instr = instr
        self.params = HyperParams(config_loc)
        os.environ['PROMPT_CHANCES'] = str(self.max_prompt)

        self.legacy_text = ''
        instrs = ' '.join(self.compile_instr)
        logger.info(f'instr={instrs}')
        logger.info(f'Retrieval Method={self.retrieval_method}')

        if self.enable_hammer:
            self.legacy_text += EXTERNAL_SAFE
            self.head_steps += 4
            
        
        self.legacy_text += TOOLS
        self.head_steps += 2

        self.legacy_text += legacy_text
        self.legacy_len = len(self.legacy_text)
        
        # 我们需要保留剩下的 proved text.
        self.legacy_text_cont = legacy_text_cont

        self.extra_bad_keywords = []
        self.hammer_bugs = []
        if "branch-check-dense" in config_loc:
            print('here')
            self.extra_bad_keywords = [
                "Lemma", "Theorem", "Axiom"
            ]
            # benchmark-id where coqhammer has a bug
            self.hammer_bugs = [
                "0_95", "0_31", "0_64"
            ]
            if any(bug in penv_dup.fpath for bug in self.hammer_bugs):
                print('modify retrieval')
                self.params.config['retrieval_method'] = 'bm25'
                    

    def get_param(self, param_name: str):
        return self.params.config[param_name]
    
    @property
    def tool_call_limit(self) -> int:
        return self.get_param('tool_call_limit')
    
    @property
    def retrieval_method(self) -> str:
        return self.get_param('retrieval_method')
    
    @property
    def enable_hammer(self) -> bool:
        return self.get_param('enable_hammer')

    def set_enable_hammer(self, enable: bool):
        self.params.config['enable_hammer'] = enable
    
    @property
    def enable_branch_check(self) -> bool:
        return self.get_param('enable_branch_check')
    
    @property
    def in_test(self) -> bool:
        return self.get_param('in_test')
    
    @property
    def use_docstring(self) -> bool:
        return self.get_param('use_docstring')
    
    @property
    def use_simple_mode(self) -> bool:
        return self.get_param('use_simple_mode')
    
    @property
    def use_cache(self) -> bool:
        return self.get_param('use_cache')
    
    @property
    def use_history(self) -> bool:
        return self.get_param('use_history')
    
    @property
    def max_explore_limit(self) -> int:
        return self.get_param('max_explore_limit')
    
    @property
    def max_prompt(self) -> int:
        return self.get_param('max_prompt')
    
    @property
    def model(self) -> ModelHub:
        return self.get_param('model')
    
    @property
    def llm_config(self) -> Dict[str, int]:
        return self.get_param('llm_config')

    @property
    def max_iter(self) -> int:
        return self.get_param('max_iter')
    
    @property
    def use_print_tool(self) -> bool:
        return self.get_param('use_print_tool')
    
    @property
    def use_proposition_form(self) -> bool:
        return self.get_param('use_proposition_form')
    
    @property
    def max_decision_num(self) -> int:
        return self.get_param('max_decision_num')
    
    @property
    def eval_call_limit(self) -> int:
        return self.get_param('eval_call_limit')

    @property
    def retain_legacy_text_cont(self) -> bool:
        return self.get_param('retain_legacy_text_cont')
    
    @property
    def scratch_everytime(self) -> bool:
        return self.get_param('scratch_everytime')

    @property
    def use_examples(self) -> bool:
        return self.get_param('use_examples')

    def overwrite(self, content: str, **kwargs):
        fpath = self.penv_dup.fpath
        with open(fpath, 'w') as f: f.write(content)

    def update_dup(self) -> List[Step]:
        if "Set Default Goal Selector \"!\"." in self.legacy_text and "Unset Default Goal Selector." not in self.legacy_text:
            logger.info("Detected 'Set Default Goal Selector \"!\".' in legacy text. Adding 'Unset Default Goal Selector.' after legacy text.")
            self.legacy_text = self.legacy_text + "\nUnset Default Goal Selector.\n"
        self.overwrite(
            self.legacy_text + self.content,
            is_dup=True)
        try:
            with CoqFile(
                self.penv_dup.fpath,
                workspace=self.penv_dup.workspace,
                timeout=1000,
                memory_limit=_16gb
            ) as cfile:

                return cfile.steps
        except ResponseError as e:
            assert False
    
    def __update_pfsteps(self, steps: List[Step]):
        try:
            self.content = parse(steps)
        except ParseError as e:
            self.content = e.text
            steps = self.update_dup()
            try:
                self.content = parse(steps[self.legacy_steps:])
            except:
                assert False, 'Parse Error'
        
        self.pfsteps = self.update_dup()[self.legacy_steps:]

    def update_steps(self):
        steps = self.update_dup()
        self.__update_pfsteps(steps[self.legacy_steps:])

    def init_pfenv(self):
        # 运行到 thm 的位置
        steps = self.update_dup()
        lsteps = len(steps) - 1
        self.legacy_text = ''.join([
            step.text for step in steps[:lsteps]
        ])
        self.content = ''.join([
            step.text for step in steps[lsteps:]
        ])
        self.legacy_len = len(self.legacy_text)
        self.legacy_steps = lsteps
        self.__update_pfsteps(steps[lsteps:])
        self.overwrite(self.legacy_text, is_dup=True)

    def update_content(self, new_content: str, upd_steps: bool=True):
        self.content = new_content
        #logger.log(15, f'[New Content]\n{self.legacy_text + self.content}')
        if upd_steps:
            return self.update_steps()
        return ''

    def hammer_dup(self, use_disk_cache=True):
        key = open(self.penv_dup.fpath, 'r').read()
        md5 = hashlib.md5(key.encode()).hexdigest()
        cpath = os.path.join(hammer_cache_dir_loc, md5)
        with open(os.path.join(get_output_dir(), 'hammers', md5), 'w') as f:
            f.write(key)
        if os.path.exists(cpath) and use_disk_cache:
            logger.info(f'Hammer cache hit {cpath}')
            with open(cpath, 'rb') as f:
                result, err = pickle.load(f)
                err = err.replace('\x00', '')
                return result, err
        logger.info(f'Hammer cache miss {cpath}')

        try:
            current_full = open(self.penv_dup.fpath, 'r').read()
        except Exception:
            assert False, 'Failed to read the proof file'
        full_script = current_full
        if self.retain_legacy_text_cont:
            if self.legacy_text_cont and self.legacy_text_cont.strip():
                # Append only if not already present to avoid duplication.
                if self.legacy_text_cont.strip() not in current_full:
                    full_script = current_full.rstrip() + '\n' + self.legacy_text_cont.lstrip()

        target_dir = os.path.dirname(self.penv_dup.fpath)
        temp_filepath = os.path.join(target_dir, 'hammer_backup.v')
        with open(temp_filepath, 'w') as f:
            f.write(current_full)
        logger.info(f"Backup Created: {temp_filepath}")

        with open(self.penv_dup.fpath, 'w') as f:
            f.write(full_script)
        
        instr = ['coqc', self.penv_dup.fpath]
        instr += self.compile_instr
        instr += [f'> {get_output_dir()}/hamlog']
        instr += [f'2> {get_output_dir()}/hamerr']
        instr = ' '.join(instr)
        logger.info(f'Instruction: {instr}')
        try:
            subprocess.run(
                instr,
                timeout=1000,
                shell=True,
                text=True,
                cwd=self.penv_dup.workspace
            )
            logger.info('Result GET')
        except:
            pass
        finally:
            shutil.copy2(temp_filepath, self.penv_dup.fpath)
            os.remove(temp_filepath)
            logger.info("Backup Restored.")
            
        result = fetch_hammer_result()
        err = ''
        hamerr_path = f'{get_output_dir()}/hamerr'
        if os.path.exists(hamerr_path):
            with open(hamerr_path, 'r') as f:
                err = f.read()
        
        # If result is actually error content (when hamlog is empty but hamerr has content)
        if isinstance(result, str) and result and 'Error:' in result:
            err = result
            result = None
            
        if use_disk_cache:
            logger.info(f'Hammer cache save {cpath}')
            os.makedirs(os.path.dirname(cpath), exist_ok=True)
            ic(cpath)
            with open(cpath, 'wb') as f:
                pickle.dump((result, err), f)
        logger.info(f"Hammer result:\n{result}")
        logger.info(f"Hammer error:\n{err}")
        err = err.replace('\x00', '')
        return result, err

def parse_with_range(steps: List[Step]) -> List[EStep]:
    pos = 0
    esteps = []
    last_pf_idx = 0
    bullet_indices = []
    stack: list[tuple[int, str]] = []
    active_bullet = [set()]

    texts = ''
    for step in steps:
        expr = get_expr(step)
        if expr is None:
            raise ParseError(texts)
        texts += step.text

    
    for idx, step in enumerate(steps):
        expr = get_expr(step)
        expr = expr[1] # As the 0-index is always VernacSynterp

        estep = EStep(step, idx, 0, idx - 1, idx + 1, pos)
        pos += len(step.text)
        esteps.append(estep)

        ttype = _term_type(expr)
        VernacType = expr[0]

        if may_intro(ttype):
            last_pf_idx = idx
            stack = []
            bullet_indices = [idx]
            active_bullet = [set()]
        
        if estep.text.lstrip().rstrip() == 'Proof.':
            bullet_indices.append(idx)

        esteps[idx].thm_idx = last_pf_idx
        esteps[idx].lb_idx = bullet_indices[-1] if bullet_indices else idx - 1

        if VernacType == 'VernacSubproof':
            stack.append((idx, 'VernacSubproof'))
            bullet_indices.append(idx)
            active_bullet.append(set())
    
        elif VernacType == 'VernacEndSubproof':
            while stack[-1][1] != 'VernacSubproof':
                id, text = stack[-1]
                if text.startswith('_B '):
                    active_bullet[-1].remove(text)
                esteps[id].nblock_idx = idx
                stack.pop()

                while bullet_indices and (id <= bullet_indices[-1]):
                    bullet_indices.pop()
            
            id, text = stack[-1]
            esteps[id].nblock_idx = idx
            stack.pop()
            active_bullet.pop()
            while bullet_indices and (id <= bullet_indices[-1]):
                bullet_indices.pop()
        
        elif VernacType == 'VernacBullet':
            bullet = esteps[idx].text.lstrip().rstrip()
            btext = f'_B {bullet}'
            if btext in active_bullet[-1]:
                while stack[-1][1] != btext:
                    id, text = stack[-1]
                    if text.startswith('_B '):
                        active_bullet[-1].remove(text)
                    esteps[id].nblock_idx = idx
                    stack.pop()
                    while bullet_indices and (id <= bullet_indices[-1]):
                        bullet_indices.pop()

                
                id, text = stack[-1]
                esteps[id].nblock_idx = idx
                stack.pop()
                while bullet_indices and (id <= bullet_indices[-1]):
                    bullet_indices.pop()
            
            stack.append((idx, btext))
            active_bullet[-1].add(btext)
            bullet_indices.append(idx)
        
        elif VernacType in ['VernacEndProof', 'VernacExactProof']:
            while len(stack) > 0:
                id, text = stack[-1]
                if text == 'VernacSubproof':
                    active_bullet.pop()
                if text.startswith('_B '):
                    active_bullet[-1].remove(text)
                esteps[id].nblock_idx = idx
                stack.pop()
                while bullet_indices and (id <= bullet_indices[-1]):
                    bullet_indices.pop()

        else:
            stack.append((idx, 'Tactic'))

    return esteps

def de_comment(src: str):
    """
    Parse a Coq script `src`, extract all nested comments, and return
    a pair (comments, stripped_src) where:
      - comments is a list of comment substrings (including the (* ... *) markers)
      - stripped_src is the original script with all those comments removed.
    """
    comments = ''
    out_chars = ''
    i = 0
    n = len(src)

    while i < n:
        # look for the start of a comment
        if i + 1 < n and src[i] == '(' and src[i+1] == '*':
            start = i
            depth = 1
            i += 2
            # consume until matching top-level "*)"
            while i < n and depth > 0:
                if i + 1 < n and src[i] == '(' and src[i+1] == '*':
                    depth += 1
                    i += 2
                elif i + 1 < n and src[i] == '*' and src[i+1] == ')':
                    depth -= 1
                    i += 2
                else:
                    i += 1
            # slice out the full comment, record it
            comment = src[start:i]
            comments += comment + '\n'
            # do NOT copy it into out_chars (i.e. we strip it)
        else:
            # normal code character, keep it
            out_chars += src[i]
            i += 1

    return comments, out_chars   

def parse_simple(steps: List[Step]) -> str:
    texts = '\n'
    cleaned = True
    results: List[Step] = []
    reason = ''
    for idx, step in enumerate(steps):
        if get_expr(step) is None:
            logger.info(f'Parsing Step {idx}: {step.text.lstrip().rstrip()}')
            reason += 'Catch syntax error.\n'
            cleaned = False
            break
        comment, tactic = de_comment(step.text)
        comment = comment.strip()
        if comment:
            comment += '\n'
        tactic = tactic.strip()
        expr = get_expr(step)
        # As I debugged, expr[0] is always 'VernacSynterp'
        # We should continue from expr[1]
        expr = expr[1]
        # logger.info(f"Expr after removing VernacSynterp: {expr[0]}")
        if expr[0] not in ['VernacBullet',
                           'VernacSubproof',
                           'VernacEndSubproof',
                           'VernacProof',
                           'VernacEndProof'
                        ]:
            
            add_text = comment + tactic + '\n'
            contains_auto = (
                tactic.find('auto') != -1
                or tactic.find('trivial') != -1
            )
            starts_progress = tactic.startswith('progress')
            starts_all_progress = tactic.startswith('all: progress')
            if contains_auto and not starts_progress and not starts_all_progress:
                cleaned = False
                reason += 'Catch unprogress auto.\n'
                if tactic.startswith('all:'):
                    remainder = tactic[len('all:'):].lstrip()
                    texts += f"{comment}all: progress {remainder}\n"
                else:
                    texts += comment + 'progress ' + tactic + '\n'
                continue

            texts += add_text
            results.append(step)
        else:
            reason += 'Catch bullet.\n'
            texts += comment
            cleaned = False

    if cleaned:
        return texts
    else:
        logger.info('Retry reason:\n' + reason)
        raise ParseError(texts)

    

parse = parse_simple