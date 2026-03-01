Require Import Coq.Unicode.Utf8.
Require Import List.

(*(*aaa*)bbb*)

Lemma rev_append: forall {a} (l1 l2: list a),
  rev (l1 ++ l2) = rev l2 ++ rev l1.
