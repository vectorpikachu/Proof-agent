from string import Template
from env import get_prompt_files_loc
import logging, re
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger('GenPromptInternal')
prompt_root = get_prompt_files_loc()
prompt_prove_dir = Path(f'{prompt_root}/prover')
prompt_eval_dir = Path(f'{prompt_root}/evaluator')
prompt_emb_dir = Path(f'{prompt_root}/embedding')

def pretty(a: List):
    ans = ''
    for id, i in enumerate(a): ans += f'[Element {id + 1}]\n{str(i)}\n'
    return ans

regfmt = re.compile(r'[\r\n][\r\n\s]*[\r\n]')
def normalize_newlines(text: str):
    return regfmt.sub('\n\n', text)

def load_template(file_path):
    with open(file_path, 'r') as template_file:
        return Template(template_file.read())

def fill_template(template: Template, placeholders):
    try:
        return normalize_newlines(template.substitute(placeholders))
    except KeyError as e:
        assert False, f"Error: fill_template: missing placeholder {e}"

task_prover = load_template(prompt_prove_dir / 'task.md')
task_evaluate_correctness = load_template(prompt_eval_dir / 'task_correctness.md')
task_evaluate_induction = load_template(prompt_eval_dir / 'task_induction.md')
task_evaluate_provability = load_template(prompt_eval_dir / 'task_provability.md')
task_evaluate_destruct = load_template(prompt_eval_dir / 'task_destruct.md')
task_emb = load_template(prompt_emb_dir / 'pfstate_task.md')
task_emb_simple = load_template(
    prompt_emb_dir / 'pfstate_task_simple.md'
)

class ContextItem:
    def __init__(self, title: str, content, maxlength=8192):
        self.title = title
        self.content = content
        self.maxlength = maxlength
    
    def __repr__(self):
        return (self.title + '\n\n' + str(self.content))[:self.maxlength]
    
    def render_len(self):
        return len(repr(self))

def format_list(lst: List[ContextItem], name: str) -> str:
    ans = ''
    for i, item in enumerate(lst):
        ans += f'##### {name} {i + 1}: '
        ans += repr(item)
        ans += '\n\n'
    return ans

def mk_prompt(autohead = True,
              pds: Dict[str, str | List[ContextItem]] = {},
              template: Template = task_prover) -> str:

    if autohead:
        pds['_blank'] = ''
        pds['coq_surrounding'] = '```coq'
        pds['end_surrounding'] = '```'
        pds['text_surrounding'] = '```text'
        pds['markdown_surrounding'] = '```markdown'
        pds['tactic_comment'] = '(* The tactic description here. *)'
        
        if isinstance(pds['lemmas'], list):
            pds['lemmas'] = format_list(pds['lemmas'], 'Lemma')
        if isinstance(pds['examples'], list):
            pds['examples'] = format_list(pds['examples'], 'Example')
        if isinstance(pds['definitions'], list):
            pds['definitions'] = format_list(pds['definitions'], 'Definition')

    return fill_template(template, pds)

system_prover = fill_template(
    load_template(prompt_prove_dir / 'system.md'),
    {
        '_blank': '',
        'reference': 'Relevant Definitions',
        'failing_head': 'A Previous Failing Trial',
        'defined': 'Defined Coq Script in the Same File',
        'prompt': mk_prompt(False, {
            # Deco Part Here
            '_blank': '',
            '_tactic_head': '',
            '_errmsg_head': '',
            'coq_surrounding': '',
            'end_surrounding': '',
            'text_surrounding': '',
            'tactic_comment': '',
            'markdown_surrounding': '',
            # Proof Part Here
            'coq_script': '',
            'proof_status': '',
            'proposition_form': '',
            'definitions': '',
            'lemmas': '',
            'examples': '',
            'failing_trials': '',
            'legacy_text': '',
        })
    }
)

system_prover_tools = fill_template(
    load_template(prompt_prove_dir / 'system_tools.md'),
    {
        '_blank': '',
        'reference': 'Relevant Definitions',
        'failing_head': 'A Previous Failing Trial',
        'defined': 'Defined Coq Script in the Same File',
        'prompt': mk_prompt(False, {
            # Deco Part Here
            '_blank': '',
            '_tactic_head': '',
            '_errmsg_head': '',
            'coq_surrounding': '',
            'end_surrounding': '',
            'text_surrounding': '',
            'tactic_comment': '',
            'markdown_surrounding': '',
            # Proof Part Here
            'coq_script': '',
            'proof_status': '',
            'proposition_form': '',
            'definitions': '',
            'lemmas': '',
            'examples': '',
            'failing_trials': '',
            'legacy_text': '',
        })
    }
)

system_evaluate_correctness = fill_template(
    load_template(prompt_eval_dir / 'system_correctness.md'),
    {
        '_blank': '',
        'reference': 'Relevant Definitions',
        'failing_head': 'A Previous Failing Trial',
        'defined': 'Defined Coq Script in the Same File',
        'prompt': mk_prompt(False, {
            # Deco Part Here
            '_blank': '',
            '_tactic_head': '',
            '_errmsg_head': '',
            'coq_surrounding': '',
            'end_surrounding': '',
            'text_surrounding': '',
            'tactic_comment': '',
            'markdown_surrounding': '',
            # Proof Part Here
            'coq_script': '',
            'proof_status': '',
            'proposition_form': '',
            'definitions': '',
            'lemmas': '',
            'examples': '',
            'failing_trials': '',
            'original_goal': '',
            'verified_texts': ''
        })
    }
)

system_evaluate_induction = open(
    prompt_eval_dir / 'system_induction.md',
).read()

system_evaluate_provability = open(
    prompt_eval_dir / 'system_provability.md',
).read()

system_evaluate_destruct = open(
    prompt_eval_dir / 'system_destruct.md',
).read()

system_pfstat_emb_with_history = open(
    prompt_emb_dir / 'pfstate_with_history.md',
).read()

system_pfstat_emb_wo_history = open(
    prompt_emb_dir / 'pfstate_wo_history.md',
).read()

system_lemma_emb_with_history = open(
    prompt_emb_dir / 'lemma_with_history.md',
).read()

system_lemma_emb_wo_history = open(
    prompt_emb_dir / 'lemma_wo_history.md',
).read()


system_prompts: dict[str, str | dict[bool, str]] = {
    'prover': system_prover,
    'evaluator_correctness': system_evaluate_correctness,
    'evaluator_induction': system_evaluate_induction,
    'evaluator_provability': system_evaluate_provability,
    'evaluator_destruct': system_evaluate_destruct,
    'pfstate_emb': {
        True: system_pfstat_emb_with_history,
        False: system_pfstat_emb_wo_history
    },
    'lemma_emb': {
        True: system_lemma_emb_with_history,
        False: system_lemma_emb_wo_history
    }
}

tasks: dict[str, Template | dict[bool, Template]] = {
    'prover': task_prover,
    'evaluator_correctness': task_evaluate_correctness,
    'evaluator_induction': task_evaluate_induction,
    'evaluator_provability': task_evaluate_provability,
    'evaluator_destruct': task_evaluate_destruct,
    'embedding': {
        False: task_emb_simple,
        True: task_emb
    }
}