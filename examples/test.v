Require Import List.
From Depinfo Require Import Loader.

Section my_Sec.

Lemma rev_append_2: forall {a} (l1 l2: list a),
  rev (l1 ++ l2) = rev l2 ++ rev l1.
idtac "<SEP>".
Print ist.
idtac "<SEP>".
Check list.
idtac "<SEP>".
Print eq.
idtac "<SEP>".
Check eq.
idtac "<SEP>".
Print app.
idtac "<SEP>".
Check app.
idtac "<SEP>".
Print rev.
idtac "<SEP>".
Check rev.
idtac "<SEP>".
Admitted.