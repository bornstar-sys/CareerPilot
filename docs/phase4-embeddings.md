# Phase 4: reusable local embeddings

Status: implemented and verified on Windows. Storage, scoped retrieval and
cited document answers are also implemented and verified. See progress.md for
the completed Phase 4 implementation checkpoint and pending Git publication.

## Installation

This patch assumes Phase 4 Step 1's documents.py is installed. It adds:

| File | Purpose |
| --- | --- |
| backend/src/careerpilot/embeddings.py | Validated, reusable local embedding adapter |
| backend/tests/test_embeddings.py | 30 deterministic offline tests |
| backend/scripts/embedding_demo.py | Real cached-model smoke test using document chunks |
| docs/phase4-embeddings.md | Usage, design choices, and validation notes |

Copy these files into their matching folders in D:\Projects\CareerPilot.
They do not replace the existing agent, planner, documents.py, or memory.

The existing optional dependency section should include:

```toml
[project.optional-dependencies]
dev = ["pytest==9.1.1"]
rag = ["fastembed==0.9.1", "psycopg[binary]==3.3.8"]
```

If FastEmbed is already installed from the preceding step, no installation
is needed. Otherwise run the project's .venv interpreter with
`-m pip install -e ".[dev,rag]"` from backend.

## Run on Windows

```powershell
cd D:\Projects\CareerPilot\backend
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest tests/test_embeddings.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/embedding_demo.py
```

The demo should show check=PASS, chunk_count=3, dimensions=384,
query_dimensions=384, and vector_norm=1.0 for each chunk. It performs no
Groq calls or database writes. It is a shape/provenance/normalization check,
not a retrieval-quality benchmark.

The default Windows model cache is `%LOCALAPPDATA%\CareerPilot\models`,
matching the preceding smoke test. Cached files are required by default.
If the cache is incomplete, explicitly permit a download:

```powershell
.\.venv\Scripts\python.exe scripts/embedding_demo.py --allow-download
```

A custom cache can be supplied with `--cache-dir "D:\path\models"`.

## Behavior

LocalEmbedder loads one FastEmbed model on the first nonempty embedding call
and reuses it. Importing the module and constructing the object do not import
FastEmbed or download anything. Empty chunk lists return an empty list without
loading the model. CPU inference uses two threads and batches of 16 texts.
This class is intended for sequential CLI use; server concurrency is not yet
implemented.

The selected model is BAAI/bge-small-en-v1.5, an English model with 384 output
dimensions and a 512-token context. Documents use their original chunk text.
Queries receive BGE's recommended English short-query instruction. The query
and document preprocessing policy is recorded as bge-query-instruction-l2-v1.

Outputs are immutable tuples of finite floats, normalized to unit length.
Missing/extra results, invalid dimensions, nonnumeric values, nonfinite values,
and zero vectors raise EmbeddingError. Chunk ID, filename, document ID,
content hash, and offsets remain on the original immutable DocumentChunk.
No input text is interpreted as an instruction and no skill/profile fields
are extracted or changed.

Each call accepts at most 256 chunks. Pass larger collections in smaller
batches. Duplicate chunk IDs within one call are rejected. Inputs must be
nonblank and free of NUL characters, with at most 20,000 input characters.
This character limit bounds preprocessing; the actual token limit is also
enforced and is usually much smaller.

## Preventing silent truncation

A character count is not a token count. A 1000-character chunk can exceed
the model limit, especially for unusual text. The adapter counts each full
prepared input, including query instructions and special tokens, before
inference. Oversized inputs raise TextTooLongError. Reduce chunk_size and
choose overlap smaller than chunk_size, or shorten the query, then retry.
Automatic token-aware splitting is not implemented in this step.

In FastEmbed 0.9.1, token_count() uses the inference tokenizer, which already
truncates. The adapter therefore clones that tokenizer, disables truncation
and padding only on the clone, and uses it for full-length checks. The
effective limit is the smaller of the loaded tokenizer limit and 512.
The actual inference tokenizer remains untouched. This version-specific
access is isolated in _FastEmbedBackend and must be rechecked if FastEmbed
is upgraded.

## Validation

The previous user-verified Windows checkpoint was 157 tests and 173 subtests
passing, with the real CPU embedding smoke test passing after download retries.

For this patch, Python 3.12.14 with FastEmbed 0.9.1 and pytest 9.1.1 passed:

- 30 embedding tests plus 20 ingestion tests: 50 tests and 177 subtests total.
- Real-model demo with HF_HUB_OFFLINE=1: three chunk vectors and one query vector.
- Full-length guard: 602 tokens rejected; 512 tokens accepted.
- Original inference tokenizer still configured for 512-token truncation.

The deterministic unit tests use an injected backend and require no model,
optional embedding dependencies, or network. They test failure behavior and
metadata preservation, not semantic model quality. The user subsequently verified the Windows Python 3.13 suite: 187 tests and
200 subtests at the embedding checkpoint, and 317 tests with 200 subtests after
all Phase 4 components. Eleven database tests are enabled separately. The full
repository was not available in the preparation workspace.

## Integration checkpoint

The subsequent storage step added a model/tokenizer artifact fingerprint and
runtime/preprocessing identity. Stored and query vectors must share that space.
The final embeddings.py includes this fingerprint; use the Step 3 version if
reapplying older patch archives. A remote model revision is not explicitly
pinned, so incompatible downloaded/runtime changes require reindexing.

PostgreSQL storage, document scoping, atomic replacement/deletion, traceable
retrieval and the explicit document-Q&A agent have now passed Windows checks.
The live answer demo also passed missing-evidence and empty-scope checks.
Similarity scores will require evaluation; they are not confidence percentages
and there is no universal relevance threshold. The English model should not
be presented as a verified multilingual solution.

## References

- https://pypi.org/project/fastembed/0.9.1/
- https://huggingface.co/BAAI/bge-small-en-v1.5
- https://qdrant.tech/documentation/tutorials-basics/generate-embeddings-fastembed/
- FastEmbed 0.9.1 installed source: text/onnx_text_model.py and text/text_embedding_base.py.
