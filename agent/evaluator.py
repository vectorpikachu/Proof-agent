"""Evaluator module - provides evaluation functions for proof correctness and induction."""

from agent.evaluators.correctness import eval_correctness
from agent.evaluators.induction import eval_induction, InductionEvalResult

# Re-export for backward compatibility
evaluate_correctness = eval_correctness
evaluate_induction = eval_induction

__all__ = [
    'eval_correctness', 
    'eval_induction', 
    'evaluate_correctness', 
    'evaluate_induction',
    'InductionEvalResult'
]
