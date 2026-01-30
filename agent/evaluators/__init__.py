"""Evaluators module for proof evaluation."""

from .base import EvalResult
from .correctness import eval_correctness
from .induction import eval_induction, InductionEvalResult
from .provability import eval_provability, ProvabilityEvalResult
from .destruct import eval_destruct, DestructEvalResult
from agent.state import GoalState

__all__ = [
    'EvalResult',
    'eval_correctness',
    'eval_induction',
    'InductionEvalResult',
    'eval_provability',
    'ProvabilityEvalResult',
    'eval_destruct',
    'DestructEvalResult',
    'eval_branch',
    'get_branch_evaluator',
    'get_branch_type',
    'branch_logic',
    'branch_keywords'
]


def get_branch_evaluator(branch_type: str):
    """Get the evaluator function for a given branch type.
    
    Args:
        branch_type: The type of branch ("destruct", "induction", or "general")
    
    Returns:
        The evaluator function
    
    Raises:
        ValueError: If the branch type is invalid
    """
    match branch_type:
        case "destruct":
            return eval_destruct
        case "induction":
            return eval_induction
        case "general":
            return eval_provability
        case _:
            raise ValueError(f'Invalid branch type: {branch_type}')


def eval_branch(
    branch_type: str,
    goal_prior: GoalState,
    goal_after: GoalState,
    tactics: str,
    **kwargs
) -> EvalResult:
    """Evaluate a branch based on its type.
    
    Args:
        branch_type: The type of branch ("destruct", "induction", or "general")
        goal_prior: The goal state before applying the tactics
        goal_after: The goal state after applying the tactics
        tactics: The tactics that were applied
        **kwargs: Additional arguments to pass to the evaluator
    
    Returns:
        EvalResult: The evaluation result (specific subclass depends on branch_type)
    
    Raises:
        ValueError: If the branch type is invalid
    """
    match branch_type:
        case "destruct":
            return eval_destruct(goal_prior, goal_after, tactics, **kwargs)
        case "induction":
            return eval_induction(goal_prior, goal_after, tactics, **kwargs)
        case "general":
            return eval_provability(goal_prior, goal_after, tactics, **kwargs)
        case _:
            raise ValueError(f'Invalid branch type: {branch_type}')


branch_logic = {
    "induction": {
        "keywords": ["induction", "elim"],
    },
    "destruct": {
        "keywords": ["case", "destruct"],
    },
    "general": {
        "keywords": ["apply", "pose", "assert",
        "constructor", "left", "right"],
    }
}

branch_keywords = [
    keyword
    for _, value in branch_logic.items() 
    for keyword in value["keywords"]
]

def get_branch_type(text: str) -> str | None:
    for branch_type, value in branch_logic.items():
        if any(keyword in text for keyword in value["keywords"]):
            return branch_type
    return None
