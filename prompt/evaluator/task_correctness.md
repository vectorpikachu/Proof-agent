### The Original Proof Status
<!--
This part gives the original proof state.
-->

${original_goal} ${_blank}

You have made the following progress towards proving the original state.

### Progress
<!--
This part provides the coq script that you have generated previously.
-->

${verified_text} ${_blank}

The progress above resulting in the following proof status.

### The Current Proof Status
<!-- Show the status to be proved, illustrating the goal that is remained unproven.
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

### Useful Lemmas
<!-- Lemmas that may help you finish the proof, you can directly use these lemmas in your proof. In the following format:
##### Lemma 1: ...

```coq
(* Lemma Description Here. *)
```
etc.
-->

${lemmas} ${_blank}

### Examples
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

## Previous Failing Trials

There are previous failing trials that try the following. Each failing trial is attached with error message reported by the Coq-LSP compiler.

${failing_trials} ${_blank}
