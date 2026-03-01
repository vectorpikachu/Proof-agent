Require Import Coq.Unicode.Utf8.
Require Import List.

Ltac reduce_eq := simpl; reflexivity.

Ltac revert_hyps := repeat match goal with | [H: _ |- _] => revert H end.

Theorem mult_0_plus : forall n m : nat, 0 + (S n * m) = S n * m.
Proof.
    intros n m.
    rewrite -> (plus_O_n (S n * m)).
    reflexivity.
Qed.

Lemma rev_append: forall {a} (l1 l2: list a),
  rev (l1 ++ l2) = rev l2 ++ rev l1.
Proof.
  hammer.
Qed.