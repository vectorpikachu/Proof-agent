# Proof Agent

An LLM-powered automated proof agent for Coq theorem proving with retrieval-augmented generation (RAG) capabilities.

## Overview

This project implements an intelligent proof assistant that leverages large language models to automatically generate and validate Coq proofs. The system combines neural approaches with symbolic reasoning, utilizing RAG techniques to retrieve relevant lemmas and proof patterns from codebases.

## Key Features

- **Automated Proof Generation**: Generates Coq proof scripts using LLM reasoning with iterative refinement
- **Retrieval-Augmented Generation**: BM25 and dense retrieval for finding relevant lemmas and proof patterns
- **Multi-Strategy Evaluation**: Specialized evaluators for correctness, induction, destructuring, and provability
- **Automated Hammer Integration**: Falls back to automated theorem proving when LLM approaches fail
- **CoqStoq Benchmark Support**: Built-in support for running benchmarks on CoqStoq datasets
- **Caching & Optimization**: Extensive caching of proofs, prompts, and embeddings for efficiency

## Architecture

### Core Components

**`agent/`** - Proof solving logic and state management
- `solve.py` - Main proof solving loop with iterative refinement
- `state.py` - Goal state parsing and representation
- `evaluators/` - Branch evaluation strategies (correctness, induction, destruct, provability)
- `hammer.py` - Integration with automated theorem provers

**`rag/`** - Retrieval-augmented generation infrastructure
- `bm25.py` - BM25-based keyword retrieval
- `dense.py` - Dense embedding-based retrieval
- `infra.py` - Retrieval infrastructure and indexing
- `query.py` - Query processing and result ranking

**`prompt/`** - LLM prompt generation and management
- `gen.py` - Dynamic prompt generation with context
- `llm.py` - LLM API interactions and caching
- `doc.py` - Documentation and docstring handling
- `prover/`, `evaluator/`, `suggestion/` - Specialized prompt templates

**`proof/`** - Coq proof manipulation utilities
- `localctx.py` - Local context management for proof files
- `term.py` - Term parsing and analysis
- `diagnosis.py` - Error diagnosis and recovery

**`coqstoq/`** - CoqStoq benchmark integration
- Project building, theorem extraction, and evaluation pipelines

**`experiments/`** - Experimental runners and result collection
- Benchmark runners, result comparison, and summarization tools

## Usage

### Running Tests

```bash
python main.py -r  # Run test suite
```

### Running Benchmarks

```bash
python main.py -s <split> -i <index> -c <config> -o <output-dir>
```

**Options:**
- `-s, --split`: Dataset split index
- `-i, --index`: Problem index within split
- `-c, --config`: Configuration file path (default: `configs/default.json`)
- `-t, --time-limit`: Time limit in seconds (default: 1 hour)
- `-m, --memory-limit`: Memory limit in MB (default: 2GB)
- `-o, --output-dir`: Output directory for logs and results
- `-p, --pass-id`: Pass identifier for multi-pass experiments

### Configuration

The project uses environment-specific configurations in `env.py` for different deployment contexts (local, server, etc.). Key settings include:

- Cache directories for proofs and embeddings
- LLM API endpoints and keys
- CoqStoq dataset paths
- Resource limits (time, memory)

#### API Configuration

Configure LLM API access via environment variables:

```bash
export LLM_BASE_URL="https://api.openai.com/v1"  # or your preferred endpoint
export LLM_API_KEY="your-api-key-here"
```

Optional alternative provider configurations:
```bash
export AOAI_API_KEY="your-azure-openai-key"
export AOAI_BASE_URL="your-azure-endpoint"
export YUNWU_API_KEY="your-yunwu-key"
export YUNWU_BASE_URL="your-yunwu-endpoint"
export QINGYUN_API_KEY="your-qingyun-key"
export QINGYUN_BASE_URL="your-qingyun-endpoint"
```

#### Vector Database Configuration (for RAG)

Configure Milvus/Zilliz vector database access:
```bash
export MILVUS_URI_1024="your-milvus-uri-for-1024-dim"
export MILVUS_TOKEN_1024="your-milvus-token"
export MILVUS_URI_3072="your-milvus-uri-for-3072-dim"
export MILVUS_TOKEN_3072="your-milvus-token"
```

## Workflow

1. **Context Loading**: Load target theorem and preceding proof context
2. **Retrieval**: Query RAG system for relevant lemmas and proof patterns
3. **Prompt Generation**: Construct prompts with context, goals, and retrieved examples
4. **LLM Query**: Generate proof tactics using LLM
5. **Validation**: Execute generated proof in Coq and validate correctness
6. **Evaluation**: Use specialized evaluators to assess proof progress and branch quality
7. **Iteration**: Refine proof iteratively based on feedback until completion or timeout
8. **Fallback**: Attempt automated hammer if LLM approaches fail

## Dependencies

- Python 3.x
- `coqpyt` - Python interface to Coq
- LLM API access (OpenAI-compatible endpoints)
- Coq proof assistant
- `coq-lsp` for LSP-based proof checking

## Output

The system generates comprehensive logs and artifacts:
- `stdout.log`, `stderr.log` - Standard output streams
- `runtime.log` - Detailed runtime logging
- `pfiles/` - Generated proof files
- `prompts/` - Saved prompts sent to LLM
- `hammers/` - Hammer attempt logs
- `rag-query-results/` - Retrieved lemmas and patterns
- `failing-trials/` - Failed proof attempts for debugging

## Research Context

This proof agent is designed for automated theorem proving research, supporting experiments with different retrieval strategies, evaluation methods, and LLM configurations. The modular architecture enables easy extension and experimentation with new approaches.
