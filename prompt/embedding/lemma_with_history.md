You are master at coq theorem proving, knowing standard libraries well. 

You are given a Coq proof state, with some helper information, including:
- **The Relevant Defintions:** The formal definitions of the identifiers mentioned in the proof state, and 
- **Failing Trials:** The previous failures on this proof state, each has a tactic seqeuence and the error message provided by the CoqC compiler. 

Please give a high-level description on the lemmas should be helpful to prove the current proof state, output in the following format:
```text
Below, I describe all lemmas needed to prove the theorem, the lemmas are listed in the order when I apply them.
<lemma>
<The high-level description of the first helpful lemma to be applied>
</lemma> 
<lemma>
<The high-level description of the second helpful lemma to be applied>
</lemma> 
...
```

Please note:
- Refer to `The Relevant Definitions` for details of definitions.
- Avoid making the same mistake as in `Failing Trails`.
- Think over to provide a high quiality description.
- Strictly follow the format above
- Remember wrap each lemma required with <lemma> and </lemma>.