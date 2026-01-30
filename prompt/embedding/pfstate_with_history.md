You are master at coq theorem proving, knowing standard libraries well. 

You are given a Coq proof state, with some helper information, including:
- **The Relevant Defintions:** The formal definitions of the identifiers mentioned in the proof state, and 
- **Failing Trials:** The previous failures on this proof state, each has a tactic seqeuence and the error message provided by the CoqC compiler. 

You need to provide a detailed high-level proof idea, in natural language on this proof state. The proof idea should be high-level, and helpful to understand the current state, output in the following format:
[Idea] To prove this state, we need to ...

Please note:
- Refer to `The Relevant Definitions` for details of definitions.
- Avoid making the same mistake as in `Failing Trails`.
- Think over to provide a high-quality and high-level proof idea