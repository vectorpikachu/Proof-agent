"""Provability evaluator for proof goals."""

from prompt.llm import query_llm
from prompt.gen import ChatHistory
from prompt.templates import system_evaluate_provability, task_evaluate_provability, format_list, ContextItem
from env import verbose, get_output_dir
from agent.state import GoalState
from agent.evaluators.base import EvalResult
import os
import re
from logging import getLogger
from typing import Optional, List
from prompt.util import ModelHub


logger = getLogger('Provability Evaluator')


class ProvabilityEvalResult(EvalResult):
    """Result of provability evaluation."""
    
    def __init__(
        self, 
        is_provable: bool, 
        is_uncertain: bool, 
        reason: str, 
        suggestion: Optional[str] = None
    ):
        super().__init__(reason, suggestion)
        self.is_provable = is_provable
        self.is_uncertain = is_uncertain
    
    def is_good(self) -> bool:
        """Check if the goal is provable.
        
        Returns:
            True if the goal is provable, False otherwise
        """
        return self.is_provable or self.is_uncertain
    
    def __repr__(self):
        return f"ProvabilityEvalResult(provable={self.is_provable}, uncertain={self.is_uncertain}, reason={self.reason}, suggestion={self.suggestion})"


def parse_provability_evaluation(response_text: str) -> ProvabilityEvalResult:
    """Parse the LLM response for provability evaluation.
    
    Args:
        response_text: The raw text response from the LLM
    
    Returns:
        ProvabilityEvalResult with the evaluation details
    """
    # Extract decision
    decision_match = re.search(r'### Decision\s*\n\s*\[?(PROVABLE|UNPROVABLE|UNCERTAIN)\]?', response_text, re.IGNORECASE)
    is_provable = True
    is_uncertain = False
    if decision_match:
        decision = decision_match.group(1).upper()
        is_provable = (decision == 'PROVABLE')
        is_uncertain = (decision == 'UNCERTAIN')
        
    # Extract reason
    reason_match = re.search(r'### Reason\s*\n\s*(.+?)(?=\n### |$)', response_text, re.DOTALL)
    reason = reason_match.group(1).strip() if reason_match else "No reason provided"
    
    # Extract suggestion (only if unprovable)
    suggestion = None
    if not is_provable:
        suggestion_match = re.search(r'### Suggestion\s*\n\s*(.+?)(?=\n### |$)', response_text, re.DOTALL)
        if suggestion_match:
            suggestion_text = suggestion_match.group(1).strip()
            # Don't include N/A as a suggestion
            if suggestion_text.upper() != 'N/A':
                # Extract text or coq blocks
                coq_blocks = re.findall(r'```coq\s*\n(.*?)\n```', suggestion_text, re.DOTALL)
                if coq_blocks:
                    # Use the last coq block found
                    suggestion = coq_blocks[-1].strip()
                else:
                    # If no coq block found, use the full suggestion text
                    suggestion = suggestion_text
    
    return ProvabilityEvalResult(is_provable, is_uncertain, reason, suggestion)


def eval_provability(
    goal_prior: GoalState,
    goal_after: GoalState,
    tactics: str,
    **kwargs
):
    """Evaluate whether the current proof goals are provable.
    
    Args:
        goal_prior: The goal state before applying the tactics
        goal_after: The goal state after applying the tactics
        tactics: The tactics that have been applied
    """
    
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

    task_content = task_evaluate_provability.substitute({
        'goal_prior': goal_prior.init,
        'goal_after': goal_after.all,
        'tactics': tactics,
        'definitions': definitions_str,
    })

    round_no = kwargs.get('round_no', 0) if verbose else None
    
    # Create chat history
    chat = ChatHistory([
        {'role': 'system', 'content': system_evaluate_provability},
        {'role': 'user', 'content': task_content}
    ])
    
    # Save prompt if verbose
    if verbose and round_no is not None:
        with open(os.path.join(
            get_output_dir(),
            'prompts',
            f'prompt_ev_provability_{round_no}.md'
        ), 'w') as f:
            f.write('[System]\n\n')
            f.write(chat.history[0][1])
            f.write('\n\n[User]\n\n')
            f.write(chat.history[1][1])
    
    # Get model and config
    model = kwargs.get('model', ModelHub.GPTO4Mini)
    llm_config = kwargs.get('llm_config', {})
    
    if model is None:
        logger.error('No model provided for provability evaluation')
        return ProvabilityEvalResult(
            True, False, 'No model available for evaluation', None
        )
    
    # Query LLM
    try:
        result = query_llm(
            chat,
            model,
            llm_config,
            use_disk_cache=True,
            save_name=f'result_provability_{round_no}.md' if round_no is not None else None,
        )
        
        response_text = result.message.content if result.message.content else ""
        
        # Save response if verbose
        if verbose and round_no is not None:
            with open(os.path.join(
                get_output_dir(),
                'prompts',
                f'ev_resp_provability_{round_no}.md'
            ), 'w') as f:
                f.write(response_text)
        
        # Parse the response
        eval_result = parse_provability_evaluation(response_text)
        logger.info(f'Provability evaluation: {eval_result}')
        
        return eval_result
        
    except Exception as e:
        logger.error(f'Error during provability evaluation: {e}')
        return ProvabilityEvalResult(
            True, False, f'Evaluation error: {str(e)}', None
        )

