"""Example usage of induction evaluator."""

# This is an example showing how to use the induction evaluator
# Note: This requires a model and LLM config to run

from agent.evaluators import eval_induction

# Example 1: Unreasonable induction (missing generalization for add_comm)
goal_before = """
forall n m : nat, n + m = m + n
"""

tactics_applied = """
induction n.
"""

goal_after = """
Subgoal 1:
m = m + 0

Subgoal 2 (inductive case):
forall n' : nat,
n' + m = m + n' ->
S n' + m = m + S n'
"""

# Example definitions that could help understand the structure
definitions = [
    ("plus", """
Fixpoint plus (n m : nat) : nat :=
  match n with
  | 0 => m
  | S n' => S (plus n' m)
  end.
""")
]

# To use:
# result = eval_induction(
#     goal_prior=goal_before,
#     goal_after=goal_after,
#     tactics=tactics_applied,
#     definitions=definitions,  # Optional: relevant definitions
#     model=your_model,
#     llm_config=your_llm_config,
#     round_no=0
# )
# 
# print(f"Is reasonable: {result.is_reasonable}")
# print(f"Reason: {result.reason}")
# if result.suggestion:
#     print(f"Suggested fix: {result.suggestion}")

# Example 2: Reasonable induction (with proper generalization)
goal_before_2 = """
forall n m : nat, n + m = m + n
"""

tactics_applied_2 = """
revert m. induction n. intros m.
"""

goal_after_2 = """
Subgoal 1:
forall m : nat, 0 + m = m + 0

Subgoal 2 (inductive case):
forall n' : nat,
(forall m : nat, n' + m = m + n') ->
forall m : nat, S n' + m = m + S n'
"""

# This should be evaluated as REASONABLE since m is properly generalized
# in the induction hypothesis

