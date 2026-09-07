# Research tooling inventory

| Capability | State on 2026-09-07 | Use |
|---|---|---|
| Web search/open/PDF inspection | available and smoke-tested | primary discovery and source verification |
| Perplexity MCP | exposed in the environment; prior public query returned empty | optional second search path; never sole evidence |
| Context7 MCP | exposed | software documentation lookup |
| Browser automation | available | source and offline-demo QA |
| Chrome Perplexity Companion | official Web Store item `hlgbcneanomplepojfcnclggenpcoldo` verified; installation/UI smoke pending because the browser-control provider rejected creation of a new Chrome tab | convenience only; thesis workflow does not depend on it |
| Zotero/citation MCP | not established | BibTeX plus DOI/source metadata remains the canonical path |

Citation workflow: locate a source, prefer publisher/project/official documentation, verify title/authors/year/DOI against that page, record the precise claim and location in `literature-matrix.jsonl`, then add or update BibTeX. Search snippets are discovery evidence, not final claim evidence. When only an abstract is accessible, mark `access_level=abstract`.

No additional MCP is required to begin: current web, browser and filesystem tools cover discovery, full-text/PDF inspection, provenance and BibTeX editing. A community citation server will be installed only if it closes a measured gap and its permissions/version/removal path are documented.
