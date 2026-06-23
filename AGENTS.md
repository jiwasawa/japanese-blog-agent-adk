# AGENTS.md

## 0. How to Work With Me

- Default to **English**. If the repository or file you’re editing is in another language, match that language.
- When a task is non-trivial (touches multiple files, or > ~50 lines of change), always:
  1. Propose a **plan** as a checklist.
  2. Wait for confirmation **if** the plan includes destructive or risky changes (deleting files, major refactors, schema migrations).
- Show **diff-style changes** when possible (old vs new) and summarize the impact.
- If something is ambiguous, state your **assumptions explicitly** in the answer before proceeding.

## 1. General Collaboration Rules

When I ask you to implement or modify something:

1. **Start with discovery**
   - Scan the repo for existing patterns:
     - Look for `pyproject.toml`, `requirements.txt`, `environment.yml`, `package.json`, `Dockerfile`, `Makefile`, `compose.yaml`, `README.md`.
     - Prefer **existing tools and patterns** over introducing new ones.
   - If similar code exists, **copy the style and structure**.

2. **Prefer minimal, safe changes**
   - Default to **incremental** changes rather than big bang refactors.
   - Do not rename or move many files unless explicitly asked.
   - For dangerous operations (data migration, API contract changes), propose a **migration plan** first.

3. **Always consider tests and docs**
   - If you touch logic, update or add **tests** in the same MR/PR.
   - If you add non-trivial behaviors or APIs, update or add **docs** or docstrings.

4. **Surface trade-offs**
   - When there are multiple reasonable designs, briefly name 2–3 options and recommend one, with 1-2 bullet reasons.

## 2. Coding Style & Languages

### 2.1 General

- Follow existing **linters/formatters** in the repo:
  - If you find configs (`.editorconfig`, `pyproject.toml`, `.pre-commit-config.yaml`, `.eslintrc*`, etc.), conform to them.
- If no standards are obvious:
  - Prefer **PEP8 + type hints** in Python.
  - Use **docstrings** for public functions/classes, describing inputs, outputs, and side effects.

### 2.2 Python

- Target **modern Python** (3.9+ unless the repo clearly uses another version).
- Use:
  - Type hints (`typing` / `typing_extensions`).
  - `pathlib` instead of `os.path` where reasonable.
  - `logging` instead of `print` for library code.
- Write functions that are:
  - **Pure when possible** (no hidden I/O or global state).
  - Parameterized instead of hard-coding constants (dataset paths, hyperparameters, etc.).
- Error handling:
  - Use **specific exceptions**.
  - Provide helpful error messages that mention the failing parameter/value and suggested fixes.

## 3. ML & Data Engineering Rules

When tasks involve data, training, or ML:

### 3.1 Data Handling

- **Never invent real user data**. Use synthetic or obviously fake examples.
- If you need sample data:
  - Prefer small, in-memory examples.
  - If sample files are needed, propose paths under an appropriate `examples/` or `tests/data/` folder.
- Avoid logging or exposing sensitive fields (PII, secrets) in examples or debug logs.

### 3.2 Experiment Structure

- Prefer a **config-driven** approach:
  - If the repo uses Hydra, Pydantic, YAML, or similar, integrate with that instead of adding new ad-hoc configs.
- Separate:
  - **Data loading & preprocessing**
  - **Model definition**
  - **Training loop**
  - **Evaluation & metrics**
- Ensure experiments are **reproducible**:
  - Provide ways to set random seeds.
  - Mention how to reproduce a run (CLI command, script invocation).

### 3.3 Evaluation

- Whenever you introduce or modify a model:
  - Define clear **metrics** and a small **evaluation script or function**.
  - Prefer metrics that are standard in the domain (e.g., accuracy/F1/BLEU/ROUGE for classical tasks; exact match / BLEU / custom heuristics for LLM tasks).
- If the change might affect performance:
  - Suggest **before/after comparisons** or add TODO comments with a simple evaluation plan.

## 4. LLM & Generative AI Rules

When dealing with LLMs, RAG, or generative models:

### Prompting & Safety

- Prefer **structured prompts**:
  - Clear instructions, input, and output format (e.g., JSON schema).
  - Avoid overly long narrative prompts; use bullet points and explicit constraints.
- For code-generation prompts, clearly specify:
  - Language, framework, coding style constraints, and expected file locations.
- If the system interacts with external users:
  - Mention potential **safety / abuse cases** and how they might be mitigated (moderation, content filters, rate limiting).

## 5. GPU / Performance Considerations

Assume that deployment and training often target **NVIDIA GPUs**.

- When relevant, highlight:
  - Memory footprint (batch size, sequence length, model size).
  - Opportunities for:
    - Mixed-precision (e.g., FP16/BF16).
    - Efficient serving (e.g., batching, kv-cache reuse).
- Avoid:
  - Obvious **performance anti-patterns**, like moving tensors to CPU and back in tight loops.
- If you propose new training or inference code:
  - Make sure device placement is clear (`.to(device)` or similar).
  - Allow configuring device via arguments or environment variables.

## 6. Project & Repo Hygiene

When adding or changing files:

1. **File placement**
   - Follow existing layout:
     - `src/` or `app/` for main code.
     - `tests/` or `*_test.py` for tests.
     - `scripts/` for CLI utilities.
   - Avoid adding top-level clutter unless necessary.

2. **Imports and dependencies**
   - Prefer internal modules over copy-pasting code.
   - Before adding a new dependency:
     - Check if something similar already exists in the project.
     - If adding, mention why it’s needed and whether it’s heavy (large or complex).

3. **Configuration**
   - Use existing configuration mechanisms (env vars, config files, CLI args).
   - Default to **safe values** (small datasets, few epochs, low concurrency) unless instructed otherwise.

## 7. Testing & Validation Rules

- Always try to provide at least one of:
  - Unit test.
  - Integration test.
  - Minimal usage example.
- Use the existing test framework:
  - Python: usually `pytest`.
  - JS/TS: Jest/Vitest or whatever is configured.
- When changing an existing function or module:
  - Identify existing tests.
  - Update them if the behavior changes.
- For LLM-related code, even simple **golden tests** (expected response patterns, JSON schema validation, etc.) are useful.

## 8. Documentation & Comments

- Update docs when:
  - Adding or changing public functions, classes, or APIs.
  - Changing CLI interfaces or configuration options.
- Prefer **short, precise comments** that explain *why* something is done, not just *what*.
- If you introduce a complex pattern (e.g., custom training loop, async RAG pipeline), add a brief **architecture comment** or a markdown note in `docs/` or `README`.

## 9. When You’re Unsure

If you’re not sure what I want:

1. State the uncertainty explicitly.
2. Offer 2–3 reasonable options with pros/cons.
3. Choose one as your default and clearly mark it, so I can override it later.

When something conflicts between this file and the existing repository conventions, **follow the repository’s existing conventions** and mention the conflict.
