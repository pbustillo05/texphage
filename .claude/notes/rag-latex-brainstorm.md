# RAG for LaTeX Package Sources — Brainstorm

*Written 2026-03-23, prompted by the `[INFRASTRUCTURE] RAG pipeline for LaTeX package sources` item in TODO.md.*

---

## 1. How useful would this be for LaTeX users generally?

**Very useful — and the gap it fills is real and currently painful.**

LaTeX has ~6,000 packages on CTAN. The documentation landscape is chaotic:
some packages have thorough manuals (TikZ/PGF runs 1,300 pages), others ship
a three-line README and a dense `.sty` with no inline comments. The *actual
ground truth* is always the `.sty` source — but finding the right line in the
right file, understanding it, and relating it to what TeX does at runtime
requires either deep expertise or a lot of time.

Current tools:
- `texdoc <pkg>`: opens the PDF manual, if one exists. No semantic search.
- `texdef -t latex -f \foo`: shows TeX's internal representation of `\foo`.
  Helpful but only if you know the macro name and have the package installed.
- CTAN web search: keyword search over package names and descriptions only,
  not over source content.
- TeX Stack Exchange: community Q&A, outstanding but asynchronous and
  increasingly hard to search for niche edge cases.
- Training data in LLMs: packages updated after the knowledge cutoff are
  unknown; even older packages are imperfectly memorised.

A RAG system over CTAN sources would fill the gap between "I know the macro
name" and "I understand exactly how it is defined and what it expands to."
Concretely:

- **Authors** could ask "what does `\DeclarePairedDelimiterX` accept as
  arguments?" and get the exact source of the definition with the argument
  spec comment, instead of navigating a 60-page mathtools PDF.
- **Package authors** debugging interactions between packages could retrieve
  both definitions side-by-side.
- **Error triage**: `undefined control sequence \foo` → query "which package
  defines `\foo`?" → get the package name, definition, and a minimal usage
  example extracted from the package's test files.
- **NLP/ML pipelines** (like texphage) that operate on LaTeX source could
  ground macro expansion in retrieved definitions rather than model memory.

The main competitors are:
1. **LLM training data**: already does this implicitly but is frozen at cutoff
   and covers only the most popular packages well.
2. **texdef**: single-macro introspection, not semantic, not document-level.
3. **Nothing**: the real current answer for most users.

The RAG system wins on freshness (re-index after CTAN updates), completeness
(all 6,000 packages, not just top-N), and queryability (semantic search over
source, not keyword search over descriptions).

**Audience estimate:** Anyone who writes non-trivial LaTeX — researchers,
engineers, publishers, large document authors. That's millions of people.
The use case is narrower than a general code search (LaTeX is a niche
language) but within that niche the pain is significant.

---

## 2. Integration with other tools

### 2a. Local deployment alongside TexLive

TexLive already ships every `.sty`/`.cls`/`.def` file in the installed
distribution. On macOS/Linux this is typically under `/usr/local/texlive/`
or `/usr/share/texlive/`. The indexing step can be done entirely from the
local filesystem — no CTAN download needed if TexLive full is installed.

**Concrete local architecture:**
```
~/.texrag/
  index/          ← Qdrant or Chroma on-disk database
  embeddings/     ← cached embedding vectors per file (for incremental update)
  metadata.json   ← package→file map, last-indexed timestamp per package
```

A `texrag index` command runs once after `tlmgr update` (or on a cron job)
and indexes any changed `.sty` files incrementally. The database is ~1–3 GB
for a full TexLive installation.

**Embedding model options for local-first:**
- `nomic-embed-text` via Ollama (free, fast on CPU for short chunks, ~270MB model)
- `text-embedding-3-small` via OpenAI API (~$5 one-time for full CTAN)
- `mxbai-embed-large` via Ollama (higher quality, ~670MB)

The local option is preferable for privacy (LaTeX source is usually not
sensitive, but the *query* — the macro you're debugging — might reveal work
in progress) and for offline use.

### 2b. Integration with coding agents, Copilot, Cursor, Claude Code

**MCP server (best path for Claude Code):**
An MCP (Model Context Protocol) server is the cleanest integration point.
The server exposes tools like:
- `latex_rag_search(query: str, top_k: int) -> list[Chunk]`
- `latex_rag_lookup(macro_name: str, package: str | None) -> list[Chunk]`
- `latex_rag_packages_defining(macro_name: str) -> list[str]`

Once the MCP server is running locally (e.g., `uvx texrag-mcp`), any
Claude Code session with `mcpServers.texrag` in `settings.json` can call
it as a tool. The agent doesn't need to know about the implementation —
it just calls the tool.

**Claude Code `.claude/settings.json` entry:**
```json
{
  "mcpServers": {
    "texrag": {
      "command": "uvx",
      "args": ["texrag-mcp", "--db", "~/.texrag/index"]
    }
  }
}
```

**VS Code LaTeX Workshop:**
LaTeX Workshop already provides IntelliSense for known commands. A RAG
backend could power hover documentation: hovering `\pgfkeys` shows the
chunk of `pgfkeys.code.tex` that defines it. This would require a
LaTeX Workshop plugin or a custom language server.

**Cursor / GitHub Copilot:**
These tools support custom context providers via their extension APIs.
For Cursor, the `@codebase` context can be supplemented with a custom
`@texrag` provider. For Copilot, GitHub's "knowledge bases" feature
(Copilot Enterprise) could be populated with CTAN sources, though this
requires hosting the sources in a GitHub repo — less ideal.

**Direct CLI tool:**
```bash
texrag query "definition of \pgfkeys argument spec"
texrag lookup '\pgfkeys' --package pgf
texrag which '\tikzset'   # → "pgf/generic/pgf/frontendlayer/tikz.code.tex"
```

This is useful standalone and also as a building block for scripted agents.

**Incremental update / TexLive integration:**
A post-update hook in `tlmgr` could trigger `texrag index --incremental`
automatically after each `tlmgr update`. This keeps the index in sync
without manual intervention.

### 2c. Cross-tool summary

| Tool | Integration mechanism | Effort |
|------|----------------------|--------|
| Claude Code | MCP server in `settings.json` | Low |
| Cursor | Custom context provider | Medium |
| VS Code + LaTeX Workshop | Custom hover provider / LSP | High |
| GitHub Copilot (Enterprise) | Knowledge base from GitHub repo | Medium |
| Any CLI / script | HTTP REST API | Low |
| texphage agents | MCP server or direct Python import | Low |

---

## 3. How easy to build with RunPod compute?

**Short answer: surprisingly easy. The hard part is chunking strategy, not compute.**

### Compute requirements

The indexing job is:
1. Parse `.sty`/`.cls` files → extract macro-definition chunks (CPU-bound, very fast)
2. Embed each chunk with an embedding model (GPU helps but not required)
3. Upsert into vector database (I/O-bound)

For the OpenAI API path, RunPod is not needed at all — you batch the chunks
and call `text-embeddings-3-small`. Cost estimate:
- Top 500 CTAN packages × average 800 macro definitions × ~400 tokens/def
  = ~160M tokens → ~$3.20 at $0.02/1M
- Full CTAN (6,000 packages): ~$40 total
- One-time cost, not per-query.

For a local model path on RunPod:
- A single A10G pod (~$0.75/hr) running `nomic-embed-text` can process
  ~50k chunks/hour via vLLM or a simple HuggingFace pipeline.
- Full CTAN: ~100k chunks → 2 hours → ~$1.50 total.
- Even cheaper than the API path.

So the compute cost is negligible. The engineering cost is in:

### Chunking strategy (the hard part)

LaTeX `.sty` files are not structured like Python or JavaScript. They use
macro expansion layers, and the "definition" of `\foo` might span 50 lines
of `\def\foo@inner#1#2{...}` helper definitions. The chunking strategy
needs to be intelligent:

**Option A: Definition-level chunking (best for macro lookup)**
- Regex-scan for `\newcommand`, `\def`, `\let`, `\DeclareDocumentCommand`,
  `\NewDocumentCommand`, `\DeclareMathOperator`, etc.
- Each definition = one chunk, with ±10 lines of surrounding context
- Metadata: macro name, package, file, line number, definition type
- Chunk count: ~200k for top 500 packages

**Option B: File-section chunking (fallback)**
- Split each `.sty` into 50-line overlapping windows
- Simpler but less precise for lookup

**Option C: Hybrid**
- Definition-level chunks for known definition patterns
- File-section chunks for files with unusual macro definition styles (e.g., expl3 `\cs_new:Npn`)

**Option D: Docs + source (richest)**
- Include `.dtx` documentation chunks alongside `.sty` source
- Many packages ship `.dtx` (documented source) files — these contain both
  code and user-facing docs interleaved. Chunking `.dtx` gives much richer
  context.

### RunPod workflow

```
1. Spin up pod: RunPod GPU Cloud → A10G 24GB, Ubuntu 22.04
2. pip install qdrant-client sentence-transformers
3. rsync or wget CTAN mirror (or use local TexLive if indexing from existing installation)
4. Run indexing script:
   python index_ctan.py \
     --source /usr/local/texlive/texmf-dist/ \
     --model nomic-embed-text \
     --output ./qdrant_snapshot/
5. Download qdrant_snapshot/ (~1-2GB) to local machine
6. Terminate pod
7. Locally: qdrant serve --snapshot ./qdrant_snapshot/
```

Total wall time: ~3 hours including setup. Total cost: ~$3. Repeat
quarterly when CTAN updates significantly.

---

## 4. Usefulness for this project — would the debugging agent love it?

**Yes, this would be the single highest-leverage infrastructure addition for the texphage agentic workflow.**

### Current pain points RAG would eliminate

The failure-taxonomy skill describes three failure modes. Mode A ("undefined
control sequence") is the one that most directly benefits:

**Current Mode A flow:**
1. Testing-agent sees `undefined_control_sequence \pgfkeys`
2. Logs BUG-N in BUGS.md with "package unknown"
3. Coding-agent picks it up, runs `texdef -t latex -f \pgfkeys`
4. Gets TeX-internal representation (often cryptic for complex macros)
5. Manually browses CTAN or uses WebFetch to get the .sty source
6. Reads the definition, writes a regex branch and test
7. Iterates because the first regex attempt often misses edge cases

**With RAG:**
1. Testing-agent sees `undefined_control_sequence \pgfkeys`
2. Calls `latex_rag_lookup('\pgfkeys')` → gets the pgfkeys.code.tex chunk
   showing the full definition including argument spec
3. The chunk is passed as context to the coding-agent prompt
4. Coding-agent writes the regex branch with the actual source in front of it
5. Far fewer iteration cycles needed

This compresses steps 3–5 of the current flow into a single tool call.
The agent no longer has to *infer* what the macro does — it sees the source.

### Impact on quarterly-audit agent

The quarterly audit scans for unrecognised macro-definition patterns and
reports them. Currently it just logs "unrecognised pattern X". With RAG:
- For each unrecognised pattern, query the RAG for the definition
- If retrieved, include the source in the audit report
- Coding-agent can immediately fix without a separate investigation step

This essentially turns Mode A from "manual investigation required" to
"automated lookup + fix generation."

### Impact on testing-agent

When a test fails with unexpected output, the testing-agent currently logs
the diff and moves on. With RAG, it could:
- Identify which macros in the failing snippet are in the dictionary
- Query for definitions of macros that are *not* in the dictionary
- Pre-populate the bug report with the relevant source snippets

This would make BUG reports self-contained and actionable from day one.

### Quantitative estimate

Based on the current BUGS.md history:
- ~60% of bugs are Mode A (undefined macro from a known package)
- Each Mode A bug currently takes 2–5 extra agent turns for lookup
- With RAG: 0–1 extra turns (just the tool call, result in context)
- Estimated turn savings: 20–40% reduction in total coding-agent turns

Given API costs and the value of faster iteration, this is a strong ROI.

### The one caveat

RAG retrieves the most *semantically similar* chunk, not necessarily the
exact right chunk. For macro definition lookup, this is mostly fine because
macro names are specific strings — a vector search for `\pgfkeys` will
reliably find the pgfkeys definition. But for complex macros spread across
many `\def\foo@inner` helpers, the agent still needs multiple retrievals and
some synthesis. So RAG is a strong accelerator, not a complete replacement
for texdef + playground investigation.

---

## 5. Implementation prompt for Opus

Below is a detailed prompt you could feed to Claude Opus (or Opus 4+) to
implement the full system. It is designed to be run in a RunPod pod or a
local machine with TexLive full installed.

---

### OPUS IMPLEMENTATION PROMPT

```
You are a senior Python engineer. Your task is to build a production-ready
RAG (Retrieval-Augmented Generation) system over LaTeX package source files.
The system must be able to run locally alongside a TexLive installation and
expose an MCP (Model Context Protocol) server for integration with Claude Code
and other AI coding tools.

## Context

LaTeX package source files (`.sty`, `.cls`, `.def`, `.code.tex`, `.dtx`)
contain macro definitions. Each macro definition is a chunk of source that
specifies how a LaTeX command is defined, what arguments it takes, and how it
expands. A RAG system over these definitions would let AI coding agents answer
"what does \foo do and how is it defined?" without relying on training data.

The primary use case is a project called texphage, which processes arXiv LaTeX
sources and needs to handle unknown macros. When the pipeline encounters
\undefined \foo, it needs to look up how \foo is defined in its package and
write a regex pattern to expand it. The RAG system provides the source context
for this lookup.

## Architecture requirements

1. **Indexer** (`texrag index`): Scans a TexLive distribution directory (or a
   CTAN mirror), extracts macro-definition chunks from .sty/.cls/.code.tex
   files, embeds them, and stores them in a local Qdrant database.

2. **Query layer** (`texrag query`): Given a query string or a macro name,
   returns the top-k most relevant chunks with metadata.

3. **MCP server** (`texrag serve`): Exposes the query layer as an MCP server
   that Claude Code can call via tools.

4. **Python library** (`import texrag`): A clean Python API usable directly
   in scripts and agents.

5. **Incremental updates**: The indexer tracks a hash per file and only
   re-embeds changed files. This makes post-tlmgr-update re-indexing fast.

---

## Detailed specification

### 1. Chunking strategy

Write a function `extract_chunks(filepath: Path) -> list[Chunk]` that:

a. Reads the file as UTF-8 (fallback to latin-1 for old files).

b. Identifies macro definition blocks using the following patterns (in order
   of priority). Each matched block becomes one chunk:

   **xparse / l3 / LaTeX3 style:**
   - `\NewDocumentCommand`, `\RenewDocumentCommand`, `\DeclareDocumentCommand`,
     `\ProvideDocumentCommand`
   - `\NewExpandableDocumentCommand`, `\RenewExpandableDocumentCommand`
   - `\cs_new:Npn`, `\cs_new_nopar:Npn`, `\cs_new_protected:Npn` (and all
     argument spec variants: `:Nn`, `:Nnn`, `:Npnn`, etc.)
   - `\cs_set:Npn`, `\cs_gset:Npn`

   **Standard LaTeX style:**
   - `\newcommand`, `\newcommand*`, `\renewcommand`, `\renewcommand*`,
     `\providecommand`, `\providecommand*`
   - `\newenvironment`, `\renewenvironment`
   - `\DeclareMathOperator`, `\DeclareMathOperator*`
   - `\DeclareRobustCommand`, `\DeclareRobustCommand*`

   **TeX primitive style:**
   - `\def`, `\edef`, `\gdef`, `\xdef`
   - `\let` (creates an alias; include the target macro name in metadata)
   - `\futurelet`
   - `\chardef`, `\mathchardef`, `\countdef`, `\dimendef`, `\skipdef`,
     `\muskipdef`, `\toksdef`
   - `\expandafter\def\csname ... \endcsname` and `\@namedef{...}` —
     mark as `definition_type = "csname_dynamic"`, set `macro_name` to the
     literal content between `\csname` and `\endcsname` (may contain spaces)

   **Keyval / pgfkeys style:**
   - `\pgfkeys{/tikz/.code=...}`, `\pgfkeys{/pgf/.code=...}` — treat each
     key definition inside a `\pgfkeys{...}` block as a separate chunk,
     with the key path in the metadata.
   - `\define@key` (from keyval package)
   - `\DeclareOption` (from LaTeX kernel)

   **Other:**
   - `\DeclareFontFamily`, `\DeclareFontShape` — font definitions
   - `\newtheorem`, `\newtheorem*`
   - `\newsavebox`, `\newlength`, `\newcounter` — register definitions

b′. **Critical:** All regex patterns matching macro names must use the character
   class `[a-zA-Z@_:*]+`, not `[a-zA-Z]+`. The `@` character is a letter inside
   `\makeatletter`/`\makeatother` blocks (standard in all `.sty` files). The `_`
   and `:` characters are letters inside `\ExplSyntaxOn`/`\ExplSyntaxOff` blocks
   (expl3). Failing to include these silently drops the majority of package
   internal definitions. Define a shared constant at the top of `chunker.py`:
   ```python
   CSNAME = r'\\[a-zA-Z@_:*]+'
   ```
   and use it in every pattern.

c. For each matched block, the chunk text is:
   - 5 lines before the definition start (for comment context)
   - The full definition block (handle nested braces: count `{` and `}` to
     find the end of the definition body, handling `\bgroup`/`\egroup` and
     escaped braces `\{`/`\}`)
   - 2 lines after the definition end

d. Metadata per chunk:
   ```python
   @dataclass
   class Chunk:
       text: str               # the raw source text
       package: str            # e.g. "pgf", "mathtools", "amsmath"
       file_path: str          # relative path within TexLive/CTAN
       macro_name: str         # e.g. r"\pgfkeys", r"\newcommand"
       definition_type: str    # "newcommand"|"def"|"cs_new"|"pgfkeys"|...
       line_start: int
       line_end: int
       aliases: list[str]      # for \let, the aliased macro names
       package_version: str    # from \ProvidesPackage{...}[date version ...]
   ```

e. Files to skip: `.ins` (installer scripts), `.dtx` prose sections (keep
   only `%    \begin{macrocode}...\end{macrocode}` blocks from `.dtx` files).
   For `.dtx` files: extract `\begin{macrocode}...\end{macrocode}` blocks,
   then apply the same definition extraction within those blocks.

f. Package name inference:
   - Prefer the name from `\ProvidesPackage{<name>}` or
     `\ProvidesFile{<name>}` in the file header.
   - Fallback: the filename without extension.
   - For files in a subdirectory like `pgf/generic/pgf/`, use the top-level
     directory name (`pgf`).

---

### 2. Embedding pipeline

Write a class `Embedder` with the following interface:

```python
class Embedder:
    def __init__(
        self,
        model: str = "nomic-embed-text",  # or "text-embedding-3-small"
        backend: Literal["ollama", "openai", "huggingface"] = "ollama",
        batch_size: int = 64,
        ollama_base_url: str = "http://localhost:11434",
        openai_api_key: str | None = None,
    ): ...

    def embed(self, texts: list[str]) -> np.ndarray: ...
    # Returns shape (N, embedding_dim)
```

For the `ollama` backend, use the Ollama HTTP API:
`POST /api/embeddings {"model": model, "prompt": text}`.
Batch by iterating with `tqdm`.

For the `openai` backend, use `openai.embeddings.create()` with batch size
up to 2048.

For the `huggingface` backend, load the model with
`sentence_transformers.SentenceTransformer(model)`.

The embedding text for each chunk should be:
```
Package: {package_name}
Macro: {macro_name}
Type: {definition_type}

{chunk_text}
```
Prepending the structured header improves retrieval accuracy for macro lookup.

---

### 3. Vector database (Qdrant)

Use Qdrant (the `qdrant-client` Python library) in local on-disk mode:
```python
from qdrant_client import QdrantClient
client = QdrantClient(path="~/.texrag/qdrant")
```

Collection schema:
- Collection name: `"latex_macros"`
- Vector size: determined from the embedding model (nomic-embed-text: 768,
  text-embedding-3-small: 1536)
- Distance: Cosine
- Payload fields (all indexed for filtered search):
  - `package: str` (keyword index)
  - `macro_name: str` (keyword index)
  - `definition_type: str` (keyword index)
  - `file_path: str`
  - `line_start: int`
  - `text: str`
  - `package_version: str`

Upsert in batches of 100. Use a stable point ID derived from
`sha256(file_path + ":" + str(line_start))[:16]` cast to int (truncate to
fit Qdrant's uint64 ID requirement).

---

### 4. Indexer CLI

```bash
texrag index \
  --source /usr/local/texlive/texmf-dist/tex/ \
  --db ~/.texrag/qdrant \
  --model nomic-embed-text \
  --backend ollama \
  --incremental          # skip files whose sha256 hasn't changed
  --top-n 500            # optional: only index the top-N CTAN packages by arXiv usage
                         # (use the package frequency list at the end of this prompt)
  --workers 4            # parallel file processing
```

The `--incremental` flag reads `~/.texrag/file_hashes.json` (a
`{file_path: sha256}` dict), skips files whose hash matches, and updates the
dict after indexing.

The `--top-n` flag uses a built-in ranked list of the top 500 packages by
frequency of appearance in arXiv math/CS papers (derive this list from CTAN
usage statistics at `https://www.ctan.org/pkg` or from a hardcoded list of
the packages that appear most frequently in arXiv LaTeX sources — the
following packages should definitely be included: amsmath, amssymb, amsthm,
geometry, graphicx, hyperref, xcolor, tikz, pgf, mathtools, physics,
siunitx, booktabs, cleveref, microtype, enumitem, babel, fontenc, inputenc,
natbib, biblatex, algorithm2e, algpseudocode, listings, minted, todonotes,
subcaption, caption, float, placeins, multirow, tabularx, longtable, array,
arydshln, xparse, etoolbox, ifthen, kvoptions, xkeyval, pgfkeys, tcolorbox,
mdframed, fancyhdr, titlesec, parskip, setspace, ulem, soul, cancel, bm,
bbm, dsfont, stmaryrd, wasysym, MnSymbol, unicode-math, fontspec, lualatex).

Log progress: `Indexed {N} chunks from {M} files in {package}.`

---

### 5. Query layer

```python
class TexRAG:
    def __init__(self, db_path: str = "~/.texrag/qdrant",
                 embedder: Embedder | None = None): ...

    def search(
        self,
        query: str,
        top_k: int = 5,
        package_filter: str | None = None,
        definition_type_filter: str | None = None,
    ) -> list[SearchResult]: ...

    def lookup_macro(
        self,
        macro_name: str,
        package: str | None = None,
        top_k: int = 3,
    ) -> list[SearchResult]: ...
    # For lookup_macro, construct query as:
    # "definition of {macro_name}" + optional package filter
    # AND do an exact keyword search on macro_name field (use Qdrant Filter)
    # Return union of semantic + exact results, deduplicated

    def packages_defining(self, macro_name: str) -> list[str]: ...
    # Exact search: Filter(must=[FieldCondition(key="macro_name",
    #   match=MatchValue(value=macro_name))])
    # Return unique package names from results

@dataclass
class SearchResult:
    chunk: Chunk
    score: float     # cosine similarity
    rank: int
```

---

### 6. MCP server

Implement an MCP server using the `mcp` Python package (from Anthropic's
`model-context-protocol` spec). The server exposes three tools:

```python
@server.tool()
def latex_rag_lookup(macro_names: list[str],
                     package: str | None = None) -> str:
    """Look up definitions of one or more LaTeX macros by name.

    Pass the surface macro AND any internal helpers you already know about
    in a single call to avoid multi-hop round-trips. For example, if you see
    \\DeclarePairedDelimiter calls \\MH_declare_paired_delimiter:Nnn, pass
    both in macro_names.

    Args:
        macro_names: List of macro names with backslash, e.g.
                     ["\\pgfkeys", "\\pgf@keys@handler"].
        package: Optional package name to restrict search.
    """
    results = []
    for name in macro_names:
        results.extend(rag.lookup_macro(name, package=package))
    return format_results(deduplicate(results))

@server.tool()
def latex_rag_search(query: str, top_k: int = 5,
                     package: str | None = None) -> str:
    """Search LaTeX package source files for macro definitions.

    Use this when you need to understand how a LaTeX macro is defined,
    what arguments it takes, or how it expands. Returns the actual .sty
    source code of the most relevant definitions.

    Args:
        query: Natural language description, e.g.
               "definition of \\pgfkeys argument spec" or
               "how does \\DeclarePairedDelimiter work in mathtools"
        top_k: Number of results to return (default 5, max 20)
        package: Optional package name to restrict search, e.g. "pgf"
    """
    results = rag.search(query, top_k=top_k, package_filter=package)
    return format_results(results)

@server.tool()
def latex_rag_which_package(macro_name: str) -> str:
    """Find which LaTeX package(s) define a given macro.

    Use this when you see an undefined control sequence error and need
    to identify which package provides the macro.

    Args:
        macro_name: The macro name with backslash, e.g. "\\sisetup".
    """
    packages = rag.packages_defining(macro_name)
    if not packages:
        return f"No package found defining {macro_name} in the index."
    return f"{macro_name} is defined in: {', '.join(packages)}"
```

Server entry point: `texrag serve --db ~/.texrag/qdrant --port 3000`

The server should be installable as a package so it can be launched with
`uvx texrag-mcp` for zero-install MCP integration.

---

### 7. Project structure

```
texrag/
  pyproject.toml          # PEP 517, entry points for texrag CLI + texrag-mcp
  README.md
  src/
    texrag/
      __init__.py          # exports TexRAG, Chunk, SearchResult
      chunker.py           # extract_chunks, brace-balanced parser
      embedder.py          # Embedder class
      indexer.py           # index CLI, incremental logic
      query.py             # TexRAG class
      mcp_server.py        # MCP server
      cli.py               # texrag CLI entry point (Typer or Click)
  tests/
    test_chunker.py        # unit tests for chunk extraction
    test_query.py          # integration tests (requires Qdrant + embedding)
    fixtures/
      sample_amsmath.sty   # 50-line excerpt with known definitions
```

---

### 8. RunPod deployment script

Write `scripts/index_on_runpod.sh`:

```bash
#!/usr/bin/env bash
# Run on a RunPod A10G pod with Ubuntu 22.04
# Usage: bash index_on_runpod.sh <output_dir>

set -euo pipefail
OUTPUT_DIR="${1:-./texrag_snapshot}"

# Install TexLive minimal + required packages
apt-get update -qq
apt-get install -y -qq texlive-full rsync

# Install Python dependencies
pip install -q texrag[ollama] qdrant-client tqdm

# Pull Ollama + nomic-embed-text
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
sleep 5
ollama pull nomic-embed-text

# Index TexLive
texrag index \
  --source /usr/share/texlive/texmf-dist/tex/ \
  --db "$OUTPUT_DIR/qdrant" \
  --model nomic-embed-text \
  --backend ollama \
  --top-n 500 \
  --workers 8

# Package the snapshot
tar -czf texrag_snapshot.tar.gz "$OUTPUT_DIR/"
echo "Done. Download texrag_snapshot.tar.gz to your local machine."
```

---

### 9. Integration guide for texphage

After building the package, document how to add it to the texphage workflow:

1. **`settings.json` entry** (add to `.claude/settings.json` in the texphage
   project):
   ```json
   {
     "mcpServers": {
       "texrag": {
         "command": "uvx",
         "args": ["texrag-mcp", "--db", "~/.texrag/qdrant"]
       }
     }
   }
   ```

2. **Skill update — failure-taxonomy**: For Mode A failures, the updated
   diagnostic path is:
   1. Call `latex_rag_which_package(\foo)` → identifies the package.
   2. Call `latex_rag_lookup([r'\foo'])` → retrieves the surface definition.
   3. If the surface definition calls an internal helper `\foo@inner` or
      `\foo_inner:Nnn`, immediately call `latex_rag_lookup([r'\foo', r'\foo@inner'])`
      in one shot — do not issue a second separate call.
   4. Append the retrieved chunks to the BUGS.md report under `## Retrieved definition`.
   5. Only fall back to `texdef` or `WebFetch` if RAG returns no results.

3. **Testing-agent update**: After identifying a Mode A failure, call
   `latex_rag_which_package(\foo)` and `latex_rag_lookup([\foo])` immediately,
   and embed the results in the BUGS.md report. This creates a zero-shot
   environment: the coding-agent starts at "write the regex" rather than
   "investigate what this macro does."

4. **xparse cheatsheet in agent prompts**: When the coding-agent receives an
   xparse definition chunk, the system prompt (or `failure-taxonomy` skill)
   must include this translation table so the agent knows how to convert the
   argument spec into a regex capture group:

   | Specifier | Meaning | Regex approach |
   |-----------|---------|----------------|
   | `m` | mandatory braced arg | balanced-brace pattern |
   | `o` | optional `[...]` | `(?:\[([^\]]*)\])?` |
   | `O{default}` | optional with default | same as `o`, absent → `default` |
   | `s` | optional star | `(\*)?` |
   | `d<d1><d2>` | delimited arg | adapted pattern for those delimiters |
   | `r<d1><d2>` | required delimited | same, no `?` |
   | `v` | verbatim arg | skip / passthrough |
   | `e{tokens}` | embellishment | one optional per token in set |

   Without this table the agent will hallucinate xparse semantics even with
   the correct source in context.

4. **Acceptance criterion from TODO.md**: For 10 Mode A bugs from known
   packages, `latex_rag_lookup` retrieves the correct definition in ≥8/10
   cases. Test this by running the texphage testing-agent on a seed set of
   papers known to trigger Mode A failures and checking that the RAG
   returned the relevant source chunk.

---

### 10. Quality and testing requirements

- 100% type annotations (Python 3.10+), mypy strict mode.
- Unit tests for `extract_chunks` using fixture `.sty` files covering:
  - `\newcommand` with 0, 1, and 2 optional args
  - `\def` with `#1#2` args
  - `\NewDocumentCommand` with xparse argument spec
  - `\cs_new:Npn` with expl3 style
  - `\pgfkeys{/tikz/.code=...}` multi-key block
  - `.dtx` file with `\begin{macrocode}` blocks
- Integration test: index the included `sample_amsmath.sty` fixture and
  verify that `lookup_macro(r"\sqrt")` returns the amsmath definition.
- Ruff for linting, Black for formatting.
- GitHub Actions CI: runs chunker unit tests (no TexLive required), skips
  indexer/query tests unless `TEXRAG_INTEGRATION=1` is set.

---

### Deliverables

1. The `texrag` Python package as described above.
2. `scripts/index_on_runpod.sh` deployment script.
3. `README.md` with quickstart (5 commands from zero to working MCP server).
4. A `texphage_integration.md` guide explaining how to wire texrag into the
   texphage Claude Code workflow (settings.json entry + skill update instructions).

Start with the `chunker.py` module and its tests. Once chunking is verified
correct on the fixture files, implement the embedder, then the indexer CLI,
then the query layer, and finally the MCP server. Do not implement the MCP
server before the query layer is tested.
```

---

---

## 6. Architectural review: blindspots and refinements

*Added 2026-03-23. These issues will surface once the chunker hits real package
sources and were identified by architectural review.*

### Blindspot 1 — Multi-hop expansion

Most surface macros immediately delegate to internal helpers with `@`/`_` names.
`\DeclarePairedDelimiter` → `\MH_declare_paired_delimiter:Nnn`. A single RAG hit
gives the surface definition but the agent still needs another turn to fetch the
internal one.

**Fix applied to the Opus prompt (§10 — tool spec):**
The `latex_rag_lookup` MCP tool should accept a *list* of macro names so the
agent can fetch a surface macro and its immediate internal dependencies in a
single tool call:
```python
def latex_rag_lookup(macro_names: list[str], package: str | None = None) -> str:
    """Look up the definitions of one or more LaTeX macros.
    Pass the surface macro AND any internal helpers you already know about
    (e.g. [r'\\foo', r'\\foo@inner']) to retrieve all definitions in one call.
    """
```
When an agent sees a surface definition that calls an internal macro, it should
add the internal name to the same call rather than issuing a second round-trip.

### Blindspot 2 — Catcode chaos / macro name characters

`expl3` uses `_` and `:` as letter-category tokens (`\ExplSyntaxOn`). Standard
LaTeX uses `@` as a letter inside packages (`\makeatletter`). A naive regex like
`\\[a-zA-Z]+` misses all of these.

**Fix applied to chunker spec (§1b):**
All definition-pattern regexes must use the character class `[a-zA-Z@_:]+` for
the macro-name token, not `[a-zA-Z]+`. This applies universally across all
definition types — not only the expl3-specific patterns — because a `\def` inside
`\makeatletter` will define `\foo@bar`.

Concretely, every pattern in the chunker that matches a macro name must use:
```python
CSNAME = r'\\[a-zA-Z@_:*]+'
```
(The `*` handles starred variants like `\newcommand*`.)

This is a single-line change to the chunker constants but prevents silently
missing a large fraction of package internals.

### Blindspot 3 — Dynamic macro generation via `\csname` / `\expandafter`

Many advanced packages do not use `\def\foo` or `\newcommand{\foo}`. They
generate macro names at expansion time:
```tex
\expandafter\def\csname foo\endcsname{...}
\@namedef{foo}{...}        % shorthand for the above
\pgfkeys{/tikz/.code=...}  % key-handler macros
```
These are invisible to definition-pattern regexes.

**Fix applied to chunker spec (§1b — additional patterns to capture):**
Add two extra chunk types:

1. **`\csname`-style defs:**
   Pattern: `\\(?:expandafter\\)?(?:def|edef|gdef|xdef)\s*\\csname\s+([^}]+)\\endcsname`
   Also: `\\@namedef\{([^}]+)\}` and `\\@nameuse`.
   The macro name in the metadata should be `\csname <content> \endcsname`
   (literal) since the actual name is only known at runtime.
   Mark `definition_type = "csname_dynamic"` — agents should treat these
   with lower confidence (retrieved definition may not match the actual
   runtime name).

2. **`pgfkeys` handlers:**
   The existing pgfkeys chunk type (already in the spec) handles this for pgf.
   For other keyval systems: add `\define@key{<family>}{<key>}` from the `keyval`
   package as a named chunk with `macro_name = "/family/key"`.

Dynamic macros will always be a partial solution — a proper fix requires a TeX
engine. Mark such chunks with `dynamic: true` in metadata so agents know to
cross-check with `texdef` rather than trusting the chunk alone.

### Strategic enhancement 1 — Pre-emptive RAG in the testing agent

When the testing-agent identifies a Mode A failure (`undefined control sequence
\foo`), it should call `latex_rag_which_package(\foo)` and then
`latex_rag_lookup([\foo])` immediately, and embed the results directly in the
`BUGS.md` report under a new `## Retrieved definition` section. This creates a
zero-shot environment for the coding-agent: the bug report contains the failing
TeX snippet, expected output, *and* the actual package source. The coding-agent
starts at "write the regex" rather than "investigate what this macro does."

**How to apply:** Update the `failure-taxonomy` skill and the testing-agent
prompt to include this step in the Mode A diagnostic path.

### Strategic enhancement 2 — xparse argument-spec translation in agent prompts

When the coding-agent receives an xparse definition (e.g.
`\NewDocumentCommand{\foo}{m O{default} m}`), the RAG chunk alone is not enough:
the agent must know how to translate xparse argument specifiers into a regex
capture group. The coding-agent system prompt (or the `failure-taxonomy` skill)
should include a compact reference table:

| Specifier | Meaning | Regex approach |
|-----------|---------|----------------|
| `m` | mandatory braced arg | `\{([^{}]*)\}` or balanced-brace pattern |
| `o` | optional `[...]` | `(?:\[([^\]]*)\])?` |
| `O{default}` | optional with default | same as `o`, treat absent as `default` |
| `s` | optional star | `(\*)?` |
| `d<delim1><delim2>` | delimited arg | adapted pattern for those delimiters |
| `r<delim1><delim2>` | required delimited | same, no `?` |

This table should live in the `failure-taxonomy` skill (or a new
`xparse-cheatsheet` skill) so agents always have it alongside the RAG result.

---

---

## 7. Gemini chunking analysis — critique and synthesis

*Added 2026-03-23. Gemini's full response was fed as input; analysis follows.*

### What Gemini got right

**§7 (Two collections) is the most important conclusion and is correct.**
`latex_api_reference` (definition-level, Use Case B) and `latex_mechanisms`
(narrative clusters + external corpora, Use Case A) should be separate
collections. The key insight Gemini made explicit that was only implicit
before: Use Case A *will fail* without external corpora that are not `.sty`
files at all — specifically **Knuth's TeXbook, `source2e.pdf`, `interface3.pdf`
(expl3 interface docs), and `macros2e.pdf`**. An AI agent trying to understand
`\expandafter` chains or `##` argument doubling cannot get there by reading
`amsmath.sty`. This corpus requirement should be added to the Opus prompt
(see update below).

**§4 (pgfkeys path-state parsing) is concrete and practical.** The
comma-splitting with depth-aware brace tracking, plus prepending the current
"directory" to each key to form the full path `/tikz/fill/.code`, is the
right approach. Emit each key-value handler as its own chunk with `macro_name
= "/tikz/fill"`. This is implementable and not previously specified.

**§5 (dtx dual-indexing) endorses the right distinction.** Prose chunks
should be indexed separately from code chunks because the *semantic density*
of .dtx prose is higher for conceptual queries. Code chunks answer "what
does the code do"; prose chunks answer "why does it work this way."

**§8 (three failure packages) are correctly identified.** TikZ semicolons,
listings catcode flip, and ifthen/etoolbox conditionals are real and the
diagnoses are accurate.

---

### Where Gemini's analysis is wrong or needs correction

#### §1 — The "AST" claim is misleading

Gemini says "a single parsing pass should build a hierarchical AST." This is
not practical and Gemini does not actually describe how to build one. A real
LaTeX AST requires a TeX engine; regex + brace counting produces at best a
heuristic tree. The correct framing is: **a two-pass heuristic scanner** — a
first pass that identifies definition-boundary candidates using the CSNAME
regex patterns, and a second pass that tries to attach surrounding prose (from
.dtx) or internal helpers (eager clustering). Do not call it an AST in the
Opus prompt; the implementer will waste time trying to build a general parser
instead of a targeted scanner.

#### §2 — The brace-balance pseudocode has three bugs

1. **Off-by-one in `\bgroup` check:** `tex_string[i+1:i+6]` gives 5
   characters. `"bgroup"` is 6 characters, so the slice should be
   `tex_string[i+1:i+7]`. As written, the check will never match. The `i
   += 7` advancement is correct (skip `\bgroup` = 7 chars), but only if the
   match guard is fixed.

2. **No word-boundary check:** `\bgroupfoo` would incorrectly match
   `\bgroup` with this code. Need to verify that the character after
   `\bgroup` is not a letter: `not tex_string[i+7:i+8].isalpha()` (or check
   for whitespace / brace / non-letter).

3. **`%` comment lines are not handled.** In any `.sty` file, a `%`
   character (outside a verbatim context) starts a comment that runs to the
   end of the line. Brace counting inside a comment will desync the depth
   counter. The algorithm must skip from `%` to the next `\n` before
   counting. This is a genuine correctness issue, not just an edge case —
   many `.sty` files have commented-out code with unbalanced braces.

The corrected pseudocode for the comment-skipping inner loop:
```python
if char == '%':
    # skip to end of line
    while i < length and tex_string[i] != '\n':
        i += 1
    continue
```
This must be inserted *before* the `\\` escape handler.

#### §3 — The lazy-retrieval "graph" metaphor undersells the cold-start problem

Gemini says: "Extract internal macro calls via regex and store them as
outgoing edges in metadata. The agent retrieves `\foo`, sees it calls
`\foo@inner`, and executes a second precise lookup."

This is correct when the internal call is a literal `\foo@inner` token in
the body. But many packages use constructed names: `\csname
foo\the\count@\endcsname`, or pass internal names through `\@nameuse`. The
regex edge-extraction step will miss these entirely. The `related_identifiers`
field in the metadata schema should be documented as **best-effort, not
exhaustive**, and the Opus prompt should say so explicitly so the implementer
doesn't over-engineer edge extraction.

#### §4 — pgfkeys path resolution is more complex than described

Gemini describes tracking `/tikz/` as the current directory and prepending
it. In practice, `\pgfkeys` supports:
- `.cd` to change the current directory mid-block
- Relative keys (no leading `/`) resolved against the current dir
- `.prefix` which prepends to all subsequent key names
- Multiple `\pgfkeys{...}` blocks that accumulate into the same keystore

The path-state parser Gemini describes handles the common case but will fail
on any package that uses `.cd` or `.prefix` within a single `\pgfkeys{...}`
block. The Opus prompt should note this limitation explicitly and recommend
that pgfkeys chunks be tagged `dynamic: partial` when the path resolution
cannot be statically determined.

#### §8 — The "fall back to double-newlines" recommendation for conditionals is wrong

Gemini says: "Fall back to chunking by double-newlines or `%` comment
breaks." Double newlines in `.sty` files do not reliably correspond to
definition boundaries — many packages are formatted without blank lines, and
many have long paragraphs of `%` comments that are broken into many short
lines. The correct fallback for a failed brace-balance extraction is:

1. Mark the chunk `is_valid: false` in metadata.
2. Include the source from the definition-start token up to a **character
   limit** (e.g., 800 chars), not to a structural boundary.
3. The agent receiving this chunk sees `is_valid: false` and knows to
   cross-check with `texdef` rather than trusting the chunk boundary.

---

### Net changes to the Opus prompt

The following concrete updates should be made to the implementation prompt
in §5 above (not repeated in full here — these are amendments):

1. **Add external corpora to the indexer** (§1 Data collection):
   In addition to `.sty`/`.cls`/`.code.tex`/`.dtx` from TexLive, the
   indexer must optionally accept a `--corpus-dir` of additional PDF/text
   sources. At minimum, the `latex_mechanisms` collection should be
   bootstrapped with the text of:
   - `interface3.pdf` (expl3 interface documentation, ~600 pages)
   - `source2e.pdf` (the LaTeX2e kernel source with commentary)
   - `texbook.pdf` if legally available (or `tex.web` from the TeX source)
   - Package manuals for the top-20 most queried packages (TikZ manual,
     mathtools, xparse, etc.)
   These are prose-first and should be chunked at the paragraph level
   (not the definition level), tagged `chunk_type: "reference_prose"`.

2. **Fix the brace-balance algorithm** (§2):
   - Change `i+1:i+6` → `i+1:i+7` for `\bgroup`/`\egroup` match
   - Add word-boundary check after `\bgroup`/`\egroup` match
   - Add `%`-comment skip before the `\\` handler

3. **Add `is_valid` flag to chunk metadata** (§6):
   Add `is_valid: bool` to the `Chunk` dataclass. Set to `False` when
   brace-balance extraction hits EOF without closing. Include `char_limit`
   fallback (800 chars from definition start) when `is_valid` is `False`.

4. **Replace "AST" language** (§1):
   Replace all references to "building an AST" with "two-pass heuristic
   scanner." The first pass finds definition boundaries; the second pass
   attaches prose context and internal-call edges.

5. **Document `related_identifiers` as best-effort** (§6):
   The `related_identifiers` field stores internal macro names found by
   literal regex scan of the definition body. Mark it `best_effort: true`
   and note that `\csname`-constructed names will not appear here.

6. **Add two collections to the architecture** (§3 vector DB):
   Qdrant should have two named collections:
   - `latex_api_reference`: definition-level chunks, Use Case B optimized.
     Payload filter indexes on `macro_name`, `package`, `visibility`.
   - `latex_mechanisms`: narrative clusters (eager-clustered surface +
     helpers), .dtx prose chunks, and reference-prose chunks from external
     corpora. Use Case A optimized.
   The MCP `latex_rag_search` tool should accept a `mode` parameter
   (`"api"` | `"concepts"` | `"both"`) to route to the right collection.

---

## Summary opinion

The RAG system is high-leverage and cheap to build. The one-time indexing
cost is under $5 (API) or $3 (local model on RunPod), the ongoing cost is
zero (local Qdrant, incremental re-index after tlmgr updates), and the MCP
integration means any Claude Code session in any project gets access to it
without code changes.

For texphage specifically, the ROI is exceptional: Mode A bugs currently
require the most agent turns, and RAG converts them from "investigate and
infer" to "retrieve and implement." The quarterly audit would become
substantially more actionable. I would move this from MEDIUM to HIGH priority
once the current BUGS.md backlog is under control.

The one prerequisite is a RunPod run (or a few hours on local hardware) to
build the initial index. Everything after that is local and free.
