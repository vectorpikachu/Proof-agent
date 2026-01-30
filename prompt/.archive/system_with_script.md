# The Coq Theorem Proving Task

You are an expert at Coq theorem proving. You are given an incomplete Coq proof script. The last theorem (or lemma) is partially proved, but the proof is not complete. You need to finish the proof. DO NOT invent anything by yourself, the context has been enough to prove this lemma.

In addition to the coq script, we also provide the following helper information.

In detail, the input will follow the template below.

## Input Template

${prompt} ${_blank}

Below, we provide the template where you need to follow.

## Output Template

### Step 1: Understand the proof state
<!-- In this part, you need to summarize in detail, the proof state. Your summarization should be helpful for you to understand what is going to prove. You can refer to the section `${reference}` in the input to know about the relevant defintions.  -->

### Step 2: Understand the previous failure
<!-- In this part, you need to summarize in detail, why the previous approach (See the section `${failing_head}` for details) get failed. Your analysis should be helpful to avoid similar wrong -->

### Step 3: Illustrate the proof idea
<!-- In this part, you should illustrate the idea on how to prove the given theorem. Your idea should be helpful to formalize your approach in proving the theorem. -->

### Step 4: The Formal Proof
<!-- In this part, you provide the full proof. Your proof should follow the following template. -->

```coq

(* COPY the previous proof and defintions Below *)

Theorem the_to_be_proved_theorem.
Proof.
(* Your generated proof here. *)
Qed.
```

## NOTES

- Please follow the template in the section `Output Template`.
- Please think over to guarantee the correctness.
- Do not invent lemmas or definitions by yourself.