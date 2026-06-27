# OKF Converter

Convert any directory of documents, code, and data into an **OKF-conformant knowledge bundle**.

**OKF** (Open Knowledge Format) is [Google Cloud's open specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) for representing knowledge as portable, cross-linked markdown that humans and AI agents can read. Announced June 2026, it formalizes [Andrej Karpathy's LLM Wiki pattern](https://github.com/karpathy/LLM-Wiki) — minimal, filesystem-native, no database required.

```
Input:  ./my-docs/                      Output: ./okf-bundle/
        ├── api-spec.yaml                       ├── index.md          ← table of contents
        ├── architecture.md                     ├── log.md            ← change log
        ├── runbook.sh                          ├── api-spec.md       ← LLM-enriched concept
        ├── report.pdf                          ├── architecture.md
        └── dataset.csv                         ├── runbook.sh.md
                                                ├── report.md
                                                ├── dataset.csv.md
                                                └── .okf_manifest.json  ← SHA-256 tracking
```

## Why OKF?

OKF bundles are:
- **Self-contained** — a directory of plain `.md` files, zero runtime dependencies
- **AI-native** — YAML frontmatter (`type`, `title`, `description`, `tags`) lets agents discover and consume knowledge without parsing
- **Portable** — version-controlled in git, synced via rsync, served from any static file server
- **Extensible** — cross-link concepts with standard markdown links; add any extra frontmatter fields you need

## Features

- **Multi-format ingestion** — code, configs, documentation, Office docs, PDFs (including scanned pages as base64 images for multimodal LLMs)
- **LLM enrichment** — each file gets auto-generated `type`, `title`, `description`, and `tags` via any OpenAI-compatible endpoint
- **Incremental sync** (`--sync`) — re-run on an evolving directory; only new/changed/deleted files are processed
- **Idempotent** — SHA-256 manifest tracks everything; unchanged files are skipped
- **Conformant** — produces standard OKF v0.1 bundles with proper frontmatter, `index.md`, `log.md`, and cross-linking
- **Dry-run** (`--dry-run`) — preview changes without writing anything

## Supported Formats

| Type | Extensions |
|------|-----------|
| **Text** | `.md` `.txt` `.rst` `.py` `.js` `.ts` `.sh` `.yaml` `.yml` `.json` `.toml` `.cfg` `.ini` `.env` |
| **Office** | `.docx` `.pptx` `.xlsx` `.xls` `.xlsm` `.csv` `.tsv` |
| **PDF** | `.pdf` (text layer + scanned pages auto-embedded as base64 PNG for multimodal LLMs) |

## Quick Start

### 1. Install

```bash
git clone https://github.com/essamrafie/okf-converter.git
cd okf-converter

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional — for Office & PDF support:
pip install python-docx python-pptx openpyxl pandas PyMuPDF xlrd tabulate
```

### 2. Convert

```bash
# Full conversion — every file becomes an OKF concept
python okf_convert.py --input ./sample-input --output ./okf-bundle

# With LLM enrichment (defaults to localhost:4000/v1, gpt-4o-mini)
python okf_convert.py --input ./sample-input --output ./okf-bundle \
    --endpoint http://my-llm-server/v1 --model qwen3-30b

# Dry-run — see what would happen
python okf_convert.py --input ./sample-input --output ./okf-bundle --dry-run
```

### 3. Sync on Changes

```bash
# After adding/editing/deleting source files:
python okf_convert.py --input ./sample-input --output ./okf-bundle --sync

# Preview before applying:
python okf_convert.py --input ./sample-input --output ./okf-bundle --sync --dry-run
```

## CLI Reference

```
usage: okf_convert.py --input INPUT --output OUTPUT [options]

required:
  --input INPUT       Source directory to scan
  --output OUTPUT     OKF bundle output path

LLM enrichment:
  --endpoint URL      OpenAI-compatible base URL (default: http://localhost:4000/v1)
  --model NAME        Model for type/title/description/tags (default: gpt-4o-mini)
  --api-key KEY       API key (or set LITELLM_API_KEY env var)

modes:
  --sync              Incremental sync — only process new/changed/deleted files
  --dry-run           Preview without writing anything
```

## How OKF Conformance Works

Every concept in the output bundle follows the [OKF v0.1 spec](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md):

### Bundle Structure
```
okf-bundle/
├── index.md              ← root listing (okf_version: "0.1" in frontmatter)
├── log.md                ← chronological change history
├── <concept>.md          ← concepts at root
└── <subdirectory>/
    ├── index.md          ← per-directory listing
    └── <concept>.md
```

### Concept Documents
Each concept is a `.md` file with delimited YAML frontmatter:

```markdown
---
type: Code Module
title: Greeting Service
description: A demo greeting module for OKF testing
tags: [demo, python, hello-world]
timestamp: 2026-06-27T12:00:00Z
source_file: sample-input/hello.py
source_format: py
---

# Content

*Source: `py`*

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```
```

### Mandatory OKF Rules (automatically satisfied)
- **M1** — Bundle is a directory of `.md` concept files ✓
- **M2** — Every concept starts with `---` delimited YAML frontmatter ✓
- **M3** — Frontmatter has non-empty `type` field ✓ (LLM-enriched or inferred from extension)
- **M6** — No runtime/database needed — just text and files ✓

### Pipeline
1. **Discover** — walks the input directory (skips `.git`, `__pycache__`, `node_modules`, etc.)
2. **Extract** — reads plain text, parses Office docs via `python-docx`/`openpyxl`/`pandas`, extracts PDF text or rasterizes scanned pages via PyMuPDF
3. **Enrich** — sends extracted content to an LLM which returns `{type, title, description, tags}`
4. **Bundle** — writes each concept as an OKF `.md` file with frontmatter + body, generates `index.md` + per-subdirectory indexes + `log.md`
5. **Track** — stores SHA-256 hashes in `.okf_manifest.json` for incremental `--sync`

## Links

| Resource | URL |
|----------|-----|
| **OKF Spec (Google Cloud)** | https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md |
| **Google Cloud Blog** | https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing |
| **OKF Conformance Suite** | https://github.com/Sudhakaran88/okf-conformance |
| **OKF Toolkit** | https://github.com/akdira/okf-toolkit |

## License

MIT
