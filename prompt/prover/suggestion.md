## Common Mistakes

When proving theorems, avoid common mistakes:
- Always choose the correct variable when applying induction.
- Do not introduce unnecessary steps. If the proof state becomes too complex, simplify and reconsider earlier steps instead of pushing forward blindly.
- Applying wrong or scarce lemmas
  Attempting to apply a lemma that is either too weak, does not fit the goal, or does not exist in the context.
- Using induction too weakly.
  Failing to generalize irrelevant variables before induction, or choosing an inappropriate induction object, often makes the induction hypothesis unusable.
- Goals becoming unprovable
  The proof path leads to contradictory or trivial goals such as `0 < 0`, `sth -> False`, or an empty `Prop`.
- Wrong manipulation of hypotheses or terms
  Misuse of `generalize`, `simpl`, `set`, `fold`, or `rewrite`, which either weakens the goal or blocks progress.
- Not using powerful available lemmas/definitions
  Missing the opportunity to apply strong lemmas or expand definitions that would simplify the proof drastically.
- Lack of appropriate proof strategies
  Sometimes failing to use proof by contradiction, case analysis, or induction on the right hypothesis leads to stuck states. -->

## Suggestions

- Ensure you have fully split necessary cases by using appropriate destruct on relevant variables. 

- When you fail in apply your induction hypothesis, consider to generalize dependent some variables or assumptions to make the hypothesis more widely applicable. Make your proof as simple as possible, e.g., use the tactics or lemma defined before.

- When you stuck after induction, you can try to induction on a different variable or assumption to see if it leads to a simpler proof. Double-check assumptions and provide necessary auxiliary lemmas when the goal is not directly provable.