"""Destruct evaluator for proof steps."""

from prompt.llm import query_llm
from prompt.gen import ChatHistory
from prompt.templates import system_evaluate_destruct, task_evaluate_destruct, format_list, ContextItem
from env import verbose, get_output_dir
from agent.state import GoalState
from agent.evaluators.base import EvalResult
import os
import re
from logging import getLogger
from typing import Optional
from prompt.util import ModelHub


logger = getLogger('Destruct Evaluator')


class DestructEvalResult(EvalResult):
    """Result of destruct evaluation."""
    
    def __init__(self, is_effective: bool, reason: str, needs_induction: bool = False, suggestion: Optional[str] = None):
        super().__init__(reason, suggestion)
        self.is_effective = is_effective
        self.needs_induction = needs_induction
    
    def is_good(self) -> bool:
        """Check if the destruct was applied effectively.
        
        Returns:
            True if destruct was effective, False otherwise
        """
        return self.is_effective and not self.needs_induction
    
    def __repr__(self):
        return f"DestructEvalResult(is_effective={self.is_effective}, needs_induction={self.needs_induction}, reason={self.reason}, suggestion={self.suggestion})"



def parse_destruct_evaluation(response_text: str) -> DestructEvalResult:
    """Parse the LLM response for destruct evaluation.
    
    Args:
        response_text: The raw text response from the LLM
    
    Returns:
        DestructEvalResult with the evaluation details
    """
    # Extract decision
    decision_match = re.search(r'### Decision\s*\n\s*\[?(EFFECTIVE|INEFFECTIVE|NEEDS_INDUCTION)\]?', response_text, re.IGNORECASE)
    is_effective = True
    needs_induction = False
    
    if decision_match:
        decision = decision_match.group(1).upper()
        is_effective = (decision == 'EFFECTIVE')
        needs_induction = (decision == 'NEEDS_INDUCTION')
        
    # Extract reason
    reason_match = re.search(r'### Reason\s*\n\s*(.+?)(?=\n### |$)', response_text, re.DOTALL)
    reason = reason_match.group(1).strip() if reason_match else "No reason provided"
    
    # Extract suggestion (if ineffective or needs induction)
    suggestion = None
    if not is_effective or needs_induction:
        suggestion_match = re.search(r'### Suggestion\s*\n\s*(.+?)(?=\n### |$)', response_text, re.DOTALL)
        if suggestion_match:
            suggestion_text = suggestion_match.group(1).strip()
            # Don't include N/A as a suggestion
            if suggestion_text.upper() != 'N/A':
                # Extract the last ```coq code block from the suggestion
                coq_blocks = re.findall(r'```coq\s*\n(.*?)\n```', suggestion_text, re.DOTALL)
                if coq_blocks:
                    # Use the last coq block found
                    suggestion = coq_blocks[-1].strip()
                else:
                    # If no coq block found, use the full suggestion text
                    suggestion = suggestion_text
    
    return DestructEvalResult(is_effective, reason, needs_induction, suggestion)


def eval_destruct(
    goal_prior: GoalState,
    goal_after: GoalState,
    tactics: str,
    **kwargs
):
    """Evaluate whether destruct was applied effectively or if induction is needed.
    
    Args:
        goal_prior: The goal state before applying destruct
        goal_after: The goal state after applying destruct
        tactics: The tactics that were applied
        **kwargs: Additional arguments including:
            - round_no: Current round number for logging
            - model: Model to use
            - llm_config: LLM config
    
    Returns:
        DestructEvalResult: Evaluation result with decision, reason, and optional suggestion
    """
    round_no = kwargs.get('round_no', 0) if verbose else None
    logger.info(f'Start Evaluate Destruct at Round {round_no}')
    
    # Combine and deduplicate definitions
    definitions = goal_prior.defs + goal_after.defs
    seen = set()
    unique_defs = []
    for name, content in definitions:
        if name not in seen:
            seen.add(name)
            unique_defs.append((name, content))
    
    definitions = [ContextItem(name, '```coq\n' + content + '\n```\n') for name, content in unique_defs]
    definitions_str = format_list(definitions, 'Definition')

    task_content = task_evaluate_destruct.substitute({
        'goal_prior': goal_prior.init,
        'goal_after': goal_after.all,
        'tactics': tactics,
        'definitions': definitions_str,
    })
    
    # Create chat history
    chat = ChatHistory([
        {'role': 'system', 'content': system_evaluate_destruct},
        {'role': 'user', 'content': task_content}
    ])
    
    # Save prompt if verbose
    if verbose and round_no is not None:
        with open(os.path.join(
            get_output_dir(),
            'prompts',
            f'prompt_ev_destruct_{round_no}.md'
        ), 'w') as f:
            f.write('[System]\n\n')
            f.write(chat.history[0][1])
            f.write('\n\n[User]\n\n')
            f.write(chat.history[1][1])
    
    # Get model and config
    model = kwargs.get('model', ModelHub.GPTO4Mini)
    llm_config = kwargs.get('llm_config', {})
    
    if model is None:
        logger.error('No model provided for destruct evaluation')
        return DestructEvalResult(True, 'No model available for evaluation', False, None)
    
    # Query LLM
    try:
        result = query_llm(
            chat,
            model,
            llm_config,
            use_disk_cache=True,
            save_name=f'result_destruct_{round_no}.md' if round_no is not None else None,
        )
        
        response_text = result.message.content if result.message.content else ""
        
        # Save response if verbose
        if verbose and round_no is not None:
            with open(os.path.join(
                get_output_dir(),
                'prompts',
                f'ev_resp_destruct_{round_no}.md'
            ), 'w') as f:
                f.write(response_text)
        
        # Parse the response
        eval_result = parse_destruct_evaluation(response_text)
        logger.info(f'Destruct evaluation: {eval_result}')
        
        return eval_result
        
    except Exception as e:
        logger.error(f'Error during destruct evaluation: {e}')
        return DestructEvalResult(True, f'Evaluation error: {str(e)}', False, None)

