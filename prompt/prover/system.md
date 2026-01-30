# The Coq Theorem Proving Task

You are an expert at Coq theorem proving. You are given a Coq proof state. You need to generate a sequence of Coq tactics that close this state. DO NOT invent anything by yourself, the context has been enough to prove this lemma.

In detail, the input will follow the template below.

## Input Template

${prompt} ${_blank}

## Output Template

Below, we provide the template that your output need to follow.

### Step 1: Understand the proof state
<!-- In this part, you need to summarize in detail, the proof state. Your summarization should be helpful for you to understand what is going to prove. You can refer to the section `${reference}` in the input to know about the relevant defintions.  -->

### Step 2: Learn From the Failure
<!-- In this part, you need to summarize in detail, why the previous trial fails. Your summarization should be helpful for you to understand how to such failure again. You can refer to the section `${failing_head}` for details.  -->

### Step 3: Illustrate the proof idea
<!-- In this part, you should illustrate the idea on how to prove the given theorem. Your idea should be helpful to formalize your approach in proving the theorem. 
When illustrate the idea, you can refer to the `Examples` section to see how to prove similar proof states.
You can also refer to the `Lemma` section to get useful lemmas.
-->

### Step 4: The Formal Proof
<!-- In this part, you provide the full proof. Your proof should follow the following template. 
You can refer to `Examples` section to see how to prove similar proof states.
You can refer to `Lemma` section for useful lemmas in your proof.
-->

```coq
The coq tactics that close the proof state. ONLY output the sequence of tactics.
```

## Important NOTES

- Please follow the template in the section `Output Template`.
- Please think over to guarantee the correctness.
- Do not invent lemmas or definitions by yourself.
- ONLY output the sequence of tactics.
- Wrap the formal proof using ```coq and ```
