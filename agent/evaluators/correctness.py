"""Correctness evaluator for proof steps."""

from prompt.llm import batch_llm
from prompt.gen import PromptInfo
from prompt.templates import system_evaluate_correctness, task_evaluate_correctness
from proof.localctx import LocalContext
from env import verbose, get_output_dir
import os
from logging import getLogger

logger = getLogger('Correctness Evaluator')


def eval_correctness(pinfo: PromptInfo, lctx: LocalContext, **kwargs):
    """Evaluate the correctness of a proof approach.
    
    Args:
        pinfo: Prompt information containing definitions and proof context
        lctx: Local context with model and configuration
        **kwargs: Additional arguments including:
            - round_no: Current round number for logging
            - original_goal: The original goal statement
            - verified_text: The verified proof text so far
    
    Returns:
        bool: True if the approach is deemed correct to proceed, False otherwise
    """
    round_no = kwargs['round_no'] if verbose else None
    original_goal = kwargs.get('original_goal', '')
    verified_text = kwargs.get('verified_text', '')

    logger.info(f'Start Evaluate at Round {round_no}')
    chat = pinfo.gen_chat(
        system_prompt=system_evaluate_correctness,
        user_template=task_evaluate_correctness,
        original_goal=original_goal,
        verified_text=verified_text,
    )
    if verbose:
        with open(os.path.join(
            get_output_dir(),
            'prompts',
            'prompt_ev_correctness_' + str(round_no) + '.md'
        ), 'w') as f:
            f.write(chat.history[-1][1])

    results = batch_llm(
        chat,
        lctx.model,
        lctx.llm_config,
        lctx.max_decision_num,
        use_disk_cache=True,
    )

    ans = 0
    for id, _raw in enumerate(results):
        raw_text = str(_raw)
        if verbose:
            file_name = os.path.join(
                get_output_dir(),
                'prompts',
                'ev_resp_' + str(kwargs['round_no']) + '_' + str(id)
            )
            with open(file_name, 'w') as f:
                f.write(raw_text)

        text = raw_text[raw_text.find('#### Decision'):].lstrip()
        if text.find('PROCEED') != -1:
            ans = ans + 1
        else:
            ans = ans - 1

    return ans > 0

