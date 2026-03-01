# Standard library imports
import os
import sys
from dataclasses import dataclass
from enum import Enum
from logging import Logger
from typing import Optional, Tuple

# Third-party imports
from coqpyt.coq.structs import Step

# Local application imports
from agent.evaluators import eval_branch, get_branch_type
from agent.hammer import try_hammer
from agent.state import (
    GoalState,
    augment_notfound_message,
    parse_state,
)
from env import coqstoq_root, get_output_dir
from proof.localctx import LocalContext
from proof.util import getscript
from prompt.gen import PromptInfo
from prompt.llm import query_llm
from prompt.util import ModelHub
from trials import TrialItem, add_item, get_trials

def valid_check(
    lctx: LocalContext, 
    final_text: str,
    logger: Logger
) -> Optional[str]:
    """
    Validate proof text by running it through Coq checker.
    
    Args:
        lctx: Local context for proof validation
        final_text: The complete proof text to validate
        logger: Logger instance for debugging output
    
    Returns:
        None if proof is valid, error message string if invalid
    """
    # Overwrite the duplicate file and run validation
    lctx.overwrite(final_text, is_dup=True)
    _, error_output = lctx.hammer_dup(use_disk_cache=True)
    
    logger.info(f'errinfo from hammer_dup: {repr(error_output)}')
    
    # Check if there's an error in the output
    if 'Error' not in error_output:
        return None
    
    # Extract the error message starting from 'Error'
    error_message = error_output[error_output.find('Error'):].strip()
    error_message = error_message.replace('\x00', '').strip()
    
    # Ignore errors about unclosed goals (these are acceptable in some contexts)
    if error_message.rstrip().endswith(
        ('needs to be closed.', 'need to be closed.')
    ):
        return None
    
    return error_message

def invalid_print(
    msg: str,
    text: str
) -> str:
    return f"""
Invalid Info: {msg}\n
Invalid Tactic: {text}\n
"""


class StopReason(Enum):
    SUCCESS = 'Proof Success'
    INVALIDSTEP = 'Invalid Step Found'
    CATCHBRANCH = 'Catch Branch'

empty_goal_state = GoalState(
    init='',
    moved='',
    raw='',
    all='',
    defs=[]
)


@dataclass
class ScanResult:
    """Result of scanning proof steps for errors and branches."""
    reason: StopReason
    steps_progress: int
    new_verified_text: str
    text_cont: str
    badstep: Optional[Step]
    errmsg: str
    branch_type: Optional[str]


def scan_proof_steps(
    lctx: LocalContext,
    verified_steps: int,
    enable_branch_check:bool,
    logger: Logger
) -> ScanResult:
    """
    Scan proof steps starting from verified_steps for errors or branch points.
    
    Returns a ScanResult with information about what was found.
    """
    reason = StopReason.SUCCESS
    badstep = None
    branch_type = None
    errmsg = 'Attempt to finish an incomplete proof.'
    new_verified_text = ''
    steps_progress = 0
    
    logger.info(f'Scan Error, {len(lctx.pfsteps)}, {verified_steps}')
    
    for step in lctx.pfsteps[verified_steps:]:
        diags = step.diagnostics
        
        # Check for errors in diagnostics
        for diag in diags:
            if diag.severity is not None and diag.severity <= 1:
                reason = StopReason.INVALIDSTEP
                logger.info(invalid_print(diag.message, step.text))
                badstep = step
                errmsg = '\n'.join([diag.message for diag in diags])
                break
        
        if reason == StopReason.INVALIDSTEP:
            break
            
        # Check for branch points
        if enable_branch_check:
            branch_type = get_branch_type(step.text)
            if branch_type is not None:
                reason = StopReason.CATCHBRANCH
                badstep = step
                logger.info(f'Catch Branch: {branch_type}')
                break
        
        # Step is valid, accumulate it
        steps_progress += 1
        new_verified_text += step.text
    
    logger.info('End Scan Error')
    text_cont = ''.join([
        step.text 
        for step in lctx.pfsteps[verified_steps + steps_progress + 1:]
    ])
    
    return ScanResult(
        reason=reason,
        steps_progress=steps_progress,
        new_verified_text=new_verified_text,
        text_cont=text_cont,
        badstep=badstep,
        errmsg=errmsg,
        branch_type=branch_type
    )


def validate_complete_proof(
    lctx: LocalContext,
    verified_text: str,
    new_verified_text: str,
    logger: Logger
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate if the proof is complete and correct.
    
    Returns:
        (is_complete, final_text, error_message)
        - is_complete: True if proof is valid and complete
        - final_text: The complete valid proof text if successful
        - error_message: Error message if validation failed
    """
    ftext = lctx.legacy_text + '\n'
    ftext += verified_text + '\n' + new_verified_text + '\nQed.'
    if lctx.retain_legacy_text_cont:
        ftext += lctx.legacy_text_cont
    
    logger.info('Calling valid_check')
    einf = valid_check(lctx, ftext, logger)
    logger.info(f'valid_check returned: {einf}')
    
    if einf is None:
        logger.info('No error found, returning ftext')
        return True, ftext, None
    
    # Parse error message
    if einf.strip().find('Attempt to save an incomplete proof') != -1:
        errmsg = 'Attempt to finish an incomplete proof.'
    else:
        errmsg = einf.strip()
    
    return False, None, errmsg


def handle_decreasing_argument_error(
    logger: Logger,
    lctx: LocalContext,
    init_goal_state: Optional[GoalState],
    verified_steps: int,
    errmsg: str
):
    """
    Handle the 'Cannot guess decreasing argument of fix' error.
    """
    if errmsg != 'Error: Cannot guess decreasing argument of fix.':
        logger.error(f'CATCH UNKNOWN ERROR: {errmsg}')
        assert False
    
    verified_tactics = ''.join(
        [step.text for step in lctx.pfsteps[1:verified_steps]]
    )
    thm_statement = lctx.pfsteps[0].text
    
    add_item(TrialItem(
        init_goal_state.init if init_goal_state is not None else '',
        verified_tactics,
        errmsg
    ))
    
    lctx.update_content(thm_statement)
    lctx.set_enable_hammer(False)

def handle_branch_catching(
    lctx: LocalContext,
    branch_type: str,
    verified_text: str,
    verified_steps: int,
    new_verified_text: str,
    badstep: Optional[Step],
    last_goal_state: Optional[GoalState],
    round_no: int,
    eval_call_num: int,
    logger: Logger
) -> Tuple[str, bool]:
    """
    Handle branch evaluation when a branch point is caught.
    
    Returns:
        (updated_verified_text, is_success)
        - updated_verified_text: The verified text after handling branch
        - is_success: True if branch evaluation passed, False otherwise
    """
    logger.info(f'Catch Branch: {branch_type}, evaluating branch')
    
    # Get the tactics text including any bad step
    badtext = badstep.text if badstep is not None else ''
    tactics_text = new_verified_text + badtext
    full_text = verified_text + tactics_text
    
    # Parse the current goal state after applying tactics
    cur_goal_state = parse_state(
        lctx,
        lctx.legacy_text + full_text,
        print_all=True
    )
    
    logger.info(f"Current Goal State parsed: {cur_goal_state}")
    logger.info(f"Last Goal State: {last_goal_state}")
    
    last_goal = last_goal_state or empty_goal_state

    select_model = lctx.model
    
    # Evaluate the branch with appropriate evaluator
    branch_eval_result = eval_branch(
        branch_type=branch_type,
        goal_prior=last_goal,
        goal_after=cur_goal_state,
        tactics=tactics_text,
        round_no=round_no,
        model=select_model,
        llm_config=lctx.llm_config
    )

    def rollback_and_add_trial():
        logger.info(f'Rolling back and adding trial: [Tactic] {tactics_text}, [Reason] {branch_eval_result.reason}\n[Suggestion] {branch_eval_result.get_suggestion()} [Last Goal] {last_goal.init}')
        lctx.update_content(verified_text)
        add_item(TrialItem(
            last_goal.init,
            tactics_text,
            branch_eval_result.reason,
        ))
    # Handle evaluation result
    if branch_eval_result.is_good():
        logger.info(f'{branch_type.capitalize()} evaluation passed, continuing')
        lctx.update_content(verified_text + tactics_text)
        return verified_text + tactics_text, True
    else:
        logger.info(f'{branch_type.capitalize()} evaluation failed, replacing tactics')
        suggestion = branch_eval_result.get_suggestion()

        
        if suggestion is not None:
            lctx.update_content(verified_text + '\n' + suggestion)
            scan_result = scan_proof_steps(
                lctx, verified_steps,
                lctx.enable_branch_check and round_no > 0, 
                logger
            )
            bad_keywords = ["Inductive", "Definition", "Context", "Variable", "Hypothesis"] + lctx.extra_bad_keywords
            match scan_result.reason:
                case StopReason.SUCCESS | StopReason.CATCHBRANCH:
                    if any(keyword in lctx.content for keyword in bad_keywords):
                        rollback_and_add_trial()
                    return verified_text, False
                case StopReason.INVALIDSTEP:
                    rollback_and_add_trial()
        else:
            rollback_and_add_trial()
        
        return verified_text, False


def check_no_such_goal_error(
    lctx: LocalContext,
    verified_text: str,
    errmsg: str,
    logger: Logger
) -> Optional[str]:
    """
    Check if error is 'No such goal' and validate if proof is actually complete.
    
    Returns the complete proof text if valid, None otherwise.
    """
    logger.info('errmsg for checking no such goal: ', errmsg)
    if errmsg.strip().find('No such goal') == -1:
        return None
    
    ftext = lctx.legacy_text + '\n' + verified_text + '\nQed.'
    einf = valid_check(lctx, ftext, logger)
    
    if einf is None:
        return ftext
    
    return None


def augment_not_found_error(
    lctx: LocalContext,
    errmsg: str,
    verified_text: str,
    logger: Logger
) -> str:
    """
    Augment 'not found in the current' error messages with more context.
    
    Returns the augmented error message.
    """
    if errmsg.strip().find('not found in the current') == -1:
        return errmsg
    
    augmented_msg = augment_notfound_message(
        errmsg,
        lctx.legacy_text + '\n' + verified_text,
        lctx.penv_dup.fpath,
        lctx.penv_dup.workspace or coqstoq_root,
        lctx.compile_instr
    )
    logger.info('Augmented not found error message:\n' + augmented_msg)
    return augmented_msg


def query_llm_for_next_tactic(
    lctx: LocalContext,
    fpath: str,
    goal_state: GoalState,
    round_no: int,
    select_model: ModelHub,
    logger: Logger
) -> str:
    """
    Create prompt and query LLM for the next tactic.
    
    Returns the suggested tactic text.
    """
    tmp_trials = get_trials(goal_state.init)
    
    logger.info('We are going to create prompt info')
    
    # Initialize defs with goal_state.defs for accumulation in tool calls
    defs = list(goal_state.defs)
    
    pinfo = PromptInfo(lctx.model, {
        'definitions': defs,
        'verified_steps': '',
        'failing_trials': tmp_trials,
        'last_goal': goal_state,
        'visible_paths': lctx.visible_paths,
        'workspace': lctx.penv_dup.workspace,
        'legacy_text': lctx.legacy_text,
        'mpath': fpath,
        'mindex': lctx.legacy_steps - lctx.head_steps,
        'round': round_no,
        'help_info': {
            'with_history': lctx.use_history,
            'trials': tmp_trials
        },
        'retrieval_method': lctx.retrieval_method,
        'use_def_tool': lctx.use_print_tool,
        'use_proposition_form': lctx.use_proposition_form,
        'use_examples': lctx.use_examples,
        'model': lctx.model,
    })
    logger.info('Prompt Info created')
    
    chat = pinfo.gen_chat()
    
    # Save prompt for debugging
    with open(os.path.join(
        get_output_dir(), 
        'prompts', f'prompt_{round_no}_0.md'
    ), 'w') as f:
        f.write('[System]\n\n')
        f.write(chat.history[0][1])
        f.write('\n\n')
        f.write('[User]\n\n')
        f.write(chat.history[1][1])
    
    logger.info(f"Preparing to query LLM for round {round_no}.")
    
    try:
        result = query_llm(
            chat, select_model, lctx.llm_config,
            use_disk_cache=lctx.use_cache,
            save_name=f'result-{round_no}_0.md',
            tools=[]
        )
        logger.info(f"LLM query successful for round {round_no}, call_num 0.")
    except Exception as e:
        logger.error(f"CRITICAL: Exception during query_llm for round {round_no}.")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        sys.exit("Exiting due to critical error in LLM query.")
    
    if result is None:
        logger.error("LLM query returned None, which should not happen after an exception. Exiting.")
        sys.exit("Exiting due to LLM query returning None post-exception.")
    
    new_text = result.message.content
    new_text = new_text if new_text is not None else ''
    new_text = getscript(new_text)
    
    return new_text


def solve(
    lctx: LocalContext,
    fpath: str,
    logger: Logger
):
    """
    Main proof solving loop. Iteratively attempts to complete a proof by:
    1. Scanning for errors or branch points
    2. Validating complete proofs
    3. Handling branches
    4. Trying hammer tactics
    5. Querying LLM for next steps
    
    Returns the complete valid proof text if successful.
    """

    init_goal_state: Optional[GoalState] = None
    last_goal_state: Optional[GoalState] = None
    verified_steps = 0
    verified_text = ''
    eval_call_num = 0
    round_no = 0
    iter_no = 0

    output_dir = get_output_dir()
    
    while iter_no < lctx.max_iter:
        logger.info('Starting Round: ' + str(round_no))
        logger.info('Iter Number: ' + str(iter_no) + "/" + str(lctx.max_iter))
        round_no += 1
        iter_no += 1
        
        # Scan proof steps for errors or branches
        scan_result = scan_proof_steps(
            lctx, verified_steps, 
            lctx.enable_branch_check and round_no > 1, 
            logger
        )
        
        logger.info('Verified Text Loaded')
        
        # Save certified proof so far
        with open(
            os.path.join(
                output_dir, 
                'cfiles',
                f'certifed_{round_no}.v'
            ), 'w'
        ) as f:
            f.write(verified_text + '\n' + scan_result.new_verified_text)
        
        # Handle SUCCESS: validate complete proof
        if scan_result.reason == StopReason.SUCCESS:
            is_valid, final_text, errmsg = validate_complete_proof(
                lctx, verified_text, scan_result.new_verified_text, logger
            )
            
            if is_valid:
                return final_text
            
            assert errmsg is not None

            if 'Cannot guess decreasing argument of fix.' in errmsg:
                handle_decreasing_argument_error(
                    logger, lctx, init_goal_state, verified_steps, errmsg
                )
                continue
        
        # Handle CATCHBRANCH: evaluate branch
        elif scan_result.reason == StopReason.CATCHBRANCH:
            assert scan_result.branch_type is not None

            eval_call_num += 1
            
            updated_text, is_success = handle_branch_catching(
                lctx=lctx,
                branch_type=scan_result.branch_type,
                verified_text=verified_text,
                verified_steps=verified_steps,
                new_verified_text=scan_result.new_verified_text,
                badstep=scan_result.badstep,
                last_goal_state=last_goal_state,
                round_no=round_no,
                eval_call_num=eval_call_num,
                logger=logger
            )
            
            verified_text = updated_text
            if is_success:
                verified_steps += scan_result.steps_progress + 1
                iter_no -= 1
                if try_hammer(lctx, verified_text, logger):
                    verified_text = lctx.content
                    verified_steps += 1
                    logger.info('Hammer worked after branch, continuing')
                    continue
                else:
                    logger.info('Hammer did not work after branch')
                    logger.info(f'text_cont: {scan_result.text_cont}')
                    lctx.update_content(
                        verified_text + scan_result.text_cont
                    )
                    continue
            else:
                continue
        
        # Handle INVALIDSTEP or incomplete proof
        else:
            errmsg = scan_result.errmsg
            
            # Check if "No such goal" actually means proof is complete
            complete_text = check_no_such_goal_error(
                lctx, verified_text, errmsg, logger
            )
            if complete_text is not None:
                return complete_text
            
            # Augment "not found" errors with more context
            errmsg = augment_not_found_error(
                lctx, errmsg, verified_text, logger
            )
        
        # Update verified text and steps
        verified_text += scan_result.new_verified_text
        verified_steps += scan_result.steps_progress
        
        # Try hammer if enabled
        logger.info('Now we are going to try hammer if enabled')
        if lctx.enable_hammer:
            if try_hammer(lctx, verified_text, logger):
                verified_text = lctx.content
                verified_steps += 1
                logger.info('Hammer worked, continuing')
                continue
            logger.info('Hammer did not work')
        else:
            lctx.set_enable_hammer(True)
        
        if scan_result.badstep is not None:
            badtext = scan_result.badstep.text
        else:
            badtext = ''
        # Parse current goal state
        logger.info('Bad Tactic & Verified Text loaded')
        goal_state = parse_state(lctx, lctx.legacy_text + verified_text)
        
        if init_goal_state is None:
            init_goal_state = goal_state
        last_goal_state = goal_state
        
        # Record failed attempt
        add_item(TrialItem(
            last_goal_state.init,
            badtext,
            errmsg,
        ))

        select_model = lctx.model
        
        # Query LLM for next tactic
        new_text = query_llm_for_next_tactic(
            lctx, fpath, goal_state, round_no, select_model, logger
        )
        lctx.update_content(verified_text + '\n' + new_text)
        
