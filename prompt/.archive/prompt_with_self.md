### The script to be proved
<!-- In this part, we provide the coq script to be proved. 
In the following format:
```coq

[Some Previous Proof and Definitions Here]

Theorem/Lemma some_to_be_proved_theorem.
Proof.
...  (* Some Partial Proofs, but incomplete *)
Qed. (* Error: Attempt to save an incomplete proof *)
```
-->

${coq_surrounding} ${_blank}
${coq_script} ${_blank}
${end_surrounding} ${_blank}

Below, we present some helper information.

#### Proof Status
<!-- Show the last proof status, illustrating the goal that is remained unproven.
In the following format:
```text
The proof status here.
```
-->

${text_surrounding} ${_blank}
${proof_status} ${_blank}
${end_surrounding} ${_blank}

#### Relevant Definitions
<!-- Relevant definitions about the proof status. In the following format:
##### Definition 1: ...

```coq
(* Defintion Here. *)
```
etc.
-->

${definitions} ${_blank}

#### Defined Coq Script in the Same File
<!-- The coq script that have been defined in the same coq file. 
You can use the definition and lemmas in this file directly.
In the following format:
```coq
(* the script *)
```
-->

${legacy_text} ${_blank}

#### Useful Lemmas
<!-- Lemmas that may help you finish the proof, you can directly use these lemmas in your proof. In the following format:
##### Lemma 1: ...

```coq
(* Lemma Description Here. *)
```
etc.
-->

${lemmas} ${_blank}

#### Examples
<!-- Examplified proofs that successfully prove other similar theorems.
In the following format:
##### Example 1: 

- Proof Status:

```text
Proof Status of the example
```

- Proof

```coq
(* The proof here *)
```

- Proof Idea

```markdown
Proof Idea here
```
etc.
-->

${examples} ${_blank}

#### Previous Failing Trial
<!-- A previous failing trial, with an error message indiciating why this trial get failed. In the following format:
- Tactic Description

```coq
(* The tactic description here. *)
```
- Error Message

```text
The error message here.
```
-->

${_tactic_head} ${_blank}

${coq_surrounding} ${_blank}
${tactic_comment} ${_blank}
${failure_tactic}
${end_surrounding}

${_errmsg_head} ${_blank}

${text_surrounding} ${_blank}
${error_message} ${_blank}
${end_surrounding} ${_blank}
