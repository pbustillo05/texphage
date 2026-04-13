Below is what I can responsibly give in one pass **without hallucinating**: a **high-recall, source-backed seed set** of tools in each category, with the detailed feature matrix you asked for where the upstream documentation is explicit. I’ve included **niche/older CTAN utilities** (even 1990s-era) and **abandoned-ish projects** where I can verify behavior from their docs.

However, “**EXTREMELY exhaustive**” across *all* of CTAN + GitHub + PyPI for two fuzzy categories is effectively an open-ended literature search. If you want truly exhaustive coverage, tell me your scope constraints and I’ll iterate (see the checklist at the end).

---

## Category 1 — LaTeX macro expansion tools (standalone text-processing; not full compilers)

### 1) **de-macro**
- **URL:** CTAN package page ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai)) (home page listed there)
- **Language:** Python ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai))
- **Maintenance / last meaningful update:** CTAN version **1.4.1**; copyright **2005–2020**; CTAN update noted **2021-04-10** ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai))  
  (This is the best “maintenance signal” CTAN exposes; it doesn’t directly expose “last git commit”.)
- **Definition types handled (per docs):**
  - **Handles:** `\newcommand`, `\renewcommand`, `\newenvironment`, `\renewenvironment` (worded as `\(re)newcommand` and `\(re)newenvironment`) ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai))
  - **Not stated / unknown from provided docs:** `\def`, `\edef`, `\let`, `\DeclareRobustCommand`, `xparse` (`\NewDocumentCommand`), etc.
- **Nested macro calls:** Not explicitly stated in CTAN summary (unknown from cited sources).
- **Cross-file expansion (`\input`/`\include`):** Not described in CTAN summary; it says it expands macros “within the document” or in a “private package file” ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai)). (So: *some* cross-file support for a specific “private package file” workflow, but details are unclear from the CTAN blurb.)
- **Known limitations (explicit):**
  - Scope is “private macros” defined via `\(re)newcommand` / `\(re)newenvironment` only (per the summary) ([ctan.org](https://ctan.org/pkg/de-macro?lang=en&utm_source=openai)).
  - Anything beyond that is not documented in the CTAN page.

**Notes for benchmarking:** de-macro is the only tool in this set that is clearly “macro-expansion oriented” rather than “file flattening”.

---

### 2) **LaTeXML (macro expansion engine, but outputs XML/HTML etc.)**
- **URL:** LaTeXML manual section on “Expansion & Macros” ([math.nist.gov](https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html?utm_source=openai))
- **Language:** (Not stated in the cited snippet; LaTeXML is commonly Perl, but I’m not asserting that without a direct source in this run.)
- **Maintenance / last meaningful update:** Not determined from the cited snippet.
- **Definition types handled:**
  - LaTeXML has its own macro definition interface (e.g., `DefMacro`) ([math.nist.gov](https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html?utm_source=openai))
  - It supports optional-argument style prototypes (e.g. `\foo[]{}`) in its macro model ([math.nist.gov](https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html?utm_source=openai))
- **Nested macro calls:** Implied (it discusses further expansion/digestion), but not a crisp yes/no statement in the snippet ([math.nist.gov](https://math.nist.gov/~BMiller/LaTeXML/manual/customization/latexml/expansion.html?utm_source=openai))
- **Cross-file expansion:** Not established from the cited snippet.
- **Known limitations:** Not captured from the cited snippet.

**Fit to your definition:** borderline. It’s *not* a full LaTeX compiler, but it’s also not a simple “replace macros with expanded text in-place” tool; it’s a conversion system with its own bindings model.

---

## Category 2 — LaTeX file flattening / unfolding tools (resolve inclusions into one file)

### 1) **latexpand** (CTAN; Perl)
- **URL:** CTAN package page ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai)) (repository also listed there)
- **Language:** Perl ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai))
- **Maintenance / last meaningful update:** CTAN version **1.7.2 (2023-02-27)** ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai))  
  (The TeX Live commit mail also shows active edits in Feb 2023.) ([tug.tug.org](https://tug.tug.org/pipermail/tex-live-commits/2023-February/024752.html?utm_source=openai))
- **Inclusion commands handled:**
  - **Handles:** `\input`, `\include` ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai))
  - **Does NOT handle:** `\includeonly` ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai))
  - (Some third-party summaries claim more, but I’m sticking to the CTAN statement for accuracy.)
- **Preserves comments:** Not specified on the CTAN package page. (Historically it can strip comments, but that behavior isn’t stated in the CTAN snippet we have, so I’m not marking it either way here.)
- **Conditional includes:** Not specified.
- **Known limitations (explicit):**
  - No `\includeonly` support ([ctan.org](https://ctan.org/pkg/latexpand?lang=en&utm_source=openai))

---

### 2) **flatten** (CTAN; lexer-based C tool via flex)
- **URL:** CTAN package page ([ctan.org](https://ctan.org/pkg/flatten?lang=en&utm_source=openai)) (with README content visible on CTAN archive page) ([ctan.org](https://ctan.org/tex-archive/support/flatten?lang=en&utm_source=openai))
- **Language:** flex/lexer source → C program ([ctan.org](https://ctan.org/tex-archive/support/flatten?lang=en&utm_source=openai))
- **Maintenance / last meaningful update:** README in the CTAN archive shows **29 October 1995** ([ctan.org](https://ctan.org/tex-archive/support/flatten?lang=en&utm_source=openai))
- **Inclusion commands handled:**
  - **Default:** `\input`, `\include` ([ctan.org](https://ctan.org/tex-archive/support/flatten?lang=en&utm_source=openai))
  - **Customizable:** “Facilities are available for modifying this set of inclusion commands.” ([ctan.org](https://ctan.org/tex-archive/support/flatten?lang=en&utm_source=openai))
- **Preserves comments:** Not stated.
- **Conditional includes:** Not stated.
- **Known limitations:** Not stated in the excerpt; likely very syntax/regex driven (lexer), but not explicitly documented in the snippet.

---

### 3) **flatex** (CTAN; C tool)
- **URL:** CTAN package page ([ctan.org](https://ctan.org/pkg/flatex?lang=en&utm_source=openai))
- **Language:** C ([ctan.org](https://ctan.org/pkg/flatex?lang=en&utm_source=openai))
- **Maintenance / last meaningful update:** CTAN lists version **1.21** ([ctan.org](https://ctan.org/pkg/flatex?lang=en&utm_source=openai)) (no date shown in the snippet)
- **Inclusion commands handled:**
  - **Handles:** `\include`, `\input` ([ctan.org](https://ctan.org/pkg/flatex?lang=en&utm_source=openai))
  - **Also includes:** `.bbl` when BibTeX is used ([ctan.org](https://ctan.org/pkg/flatex?lang=en&utm_source=openai))
- **Preserves comments:** Not stated.
- **Conditional includes:** Not stated.
- **Known limitations:** Not stated.

---

### 4) **flachtex** (PyPI; Python)
- **URL:** PyPI project page ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))
- **Language:** Python ([pypi.org](https://pypi.org/project/flachtex/0.1.4/?utm_source=openai))
- **Maintenance / last meaningful update:** Not reliably inferable as “last commit” from PyPI snippet alone; PyPI shows it exists and describes features. ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))
- **Inclusion commands handled (explicit list from PyPI docs):**
  - `\include{...}`, `\input{...}` ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))
  - `\subimport{path}{file}` and `\subimport*{path}{file}` ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))
  - Also supports a **manual directive** `%%FLACHTEX-EXPLICIT-IMPORT[...]` for cases it can’t parse ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))
- **Preserves comments:** It can **remove comments** (optional) ([pypi.org](https://pypi.org/project/flachtex/0.1.4/?utm_source=openai))
- **Conditional includes:** It explicitly mentions includes “done by an evaluation” may not be deducible; it provides a manual override instead ([pypi.org](https://pypi.org/project/flachtex/0.1.4/?utm_source=openai))
- **Known limitations (explicit):**
  - “Complex import logic that cannot be parsed” requires explicit/manual includes ([pypi.org](https://pypi.org/project/flachtex/?utm_source=openai))

---

### 5) **texdirflatten** (CTAN; Perl; can optionally produce one flattened .tex)
- **URL:** CTAN package page ([ctan.org](https://ctan.org/pkg/texdirflatten?lang=en&utm_source=openai)) (README excerpt on CTAN archive) ([ctan.org](https://ctan.org/tex-archive/support/texdirflatten?lang=en&utm_source=openai))
- **Language:** Perl ([ctan.org](https://ctan.org/tex-archive/support/texdirflatten?lang=en&utm_source=openai))
- **Maintenance / last meaningful update:** CTAN lists version **1.3** and copyright **2003–2017** ([ctan.org](https://ctan.org/pkg/texdirflatten?lang=en&utm_source=openai))
- **Inclusion commands handled:**
  - The `--onetex` mode “produces a single TeX file by expanding all `\input` and `\include` commands in place.” ([ctan.org](https://ctan.org/tex-archive/support/texdirflatten?lang=en&utm_source=openai))
- **Preserves comments:** Not stated.
- **Conditional includes:** Not stated.
- **Known limitations (explicit-ish):**
  - General “CAVEATS… take backups… no warranties” ([ctan.org](https://ctan.org/tex-archive/support/texdirflatten?lang=en&utm_source=openai))
  - It’s also primarily a **bundling** tool (collect files into one dir) rather than strictly an inliner, but it does have the `--onetex` feature. ([ctan.org](https://ctan.org/tex-archive/support/texdirflatten?lang=en&utm_source=openai))

---

### 6) **texstrip** (PyPI; depends on latexpand)
- **URL:** PyPI project page ([pypi.org](https://pypi.org/project/texstrip/?utm_source=openai))
- **Language:** Python ([pypi.org](https://pypi.org/project/texstrip/?utm_source=openai))
- **Maintenance / last meaningful update:** PyPI release history shows **0.1.1 Aug 18, 2020** ([pypi.org](https://pypi.org/project/texstrip/?utm_source=openai))
- **Inclusion commands handled:** Indirect; it explicitly says “You’ll need latexpand.” ([pypi.org](https://pypi.org/project/texstrip/?utm_source=openai))
- **Preserves comments / conditional includes / limitations:** Not described in the PyPI snippet.

---

## What I did *not* do (to avoid giving you bad data)
- I did **not** claim support for `\import`, `\inputfrom`, `\subimport` etc. for tools unless the tool docs explicitly said so. (For example, CTAN’s **import** package defines `\import`, `\subimport`, `\inputfrom`, etc. ([ctan.org](https://ctan.org/tex-archive/macros/latex/contrib/import?lang=en&utm_source=openai)), but most flatteners do **not** necessarily understand those without extra parsing rules.)
- I did **not** invent “last commit dates” for CTAN tools that don’t have public VCS metadata in the CTAN entry.

---

## If you want “EXTREMELY exhaustive”: 6 concrete scoping questions
Answer these and I’ll continue with additional web passes and produce a much larger catalog with fewer “unknowns”.

1) For **Category 1**, do you accept tools that expand macros by **running a TeX engine in expansion mode** (e.g., via `\meaning`, `\show`, `\write18`, etc.)? Or must it be **non-TeX parsing only**?
2) Do you include **AST-based tooling** (pandoc Lua filters / LaTeX parsers) if they can inline includes or rewrite macros, even if not “100% TeX-correct”?
3) Do you want tools that only expand **a subset** (e.g., only `\newcommand`), or must they also try to handle primitives like `\def` / `\let`?
4) For flattening, should tools that generate a **bundle dir** (like `texdirflatten`) count, or only those that output **one monolithic .tex**?
5) Are you targeting **LaTeX2e only**, or also **plain TeX**, **ConTeXt**, **LuaLaTeX/xelatex specifics**, etc.?
6) Output format preference: giant Markdown table vs. one tool per section with bullet-point feature flags?

If you reply with those constraints, I’ll expand the list substantially (more CTAN utilities, more GitHub scripts, and more language-specific parsers) and fill in the matrix fields with citations wherever possible.