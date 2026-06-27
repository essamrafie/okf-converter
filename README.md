# OKF Converter

Convert any directory of documents, code, and data into an **OKF-conformant knowledge bundle** — a structured set of markdown concepts with LLM-generated metadata.

```
Input:  ./my-docs/ (any mix of text, Office, PDF files)
        ├── api-spec.yaml
        ├── architecture.md
        ├── runbook.sh
        └── report.pdf

Output: ./okf-bundle/ (knowledge bundle)
        ├── index.md          ← auto-generated table of contents
        ├── log.md            ← change log with timestamps
        ├── api-spec.md       ← extracted + LLM-enriched concept
        ├── architecture.md
        ├── runbook.sh.md
        ├── report.md
        └── .okf_manifest.json  ← SHA-256 hash tracking
```

## Features

- **Multi-format ingestion** — text, code, configs, Office docs, PDFs (including scanned pages as base64 images)
- **LLM enrichment** — each file gets an auto-generated type, title, description, and tags via any OpenAI-compatible endpoint
- **Incremental sync** (`--sync`) — re-run on an evolving directory; only new/changed/deleted files are processed
- **Idempotent** — SHA-256 manifest tracks what's been done; unchanged files are skipped
- **Dry-run** (`--dry-run`) — preview changes without writing anything

## Supported Formats

| Type | Extensions |
|------|-----------|
| **Text** | `.md` `.txt` `.rst` `.py` `.js` `.ts` `.sh` `.yaml` `.yml` `.json` `.toml` `.cfg` `.ini` `.env` |
| **Office** | `.docx` `.pptx` `.xlsx` `.xls` `.xlsm` `.csv` `.tsv` |
| **PDF** | `.pdf` (text layer + scanned pages auto-embedded as base64 PNG for multimodal LLMs) |

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml requests

# Optional — for Office & PDF support:
pip install python-docx python-pptx openpyxl pandas PyMuPDF xlrd
```

### 2. Run a Conversion

```bash
# Full convert — process every file
python okf_convert.py --input ./sample-input --output ./okf-bundle

# With LLM enrichment (defaults: localhost:4000/v1, gpt-4o-mini)
python okf_convert.py --input ./sample-input --output ./okf-bundle \
    --endpoint http://my-llm-server/v1 --model qwen3-30b

# Dry-run — see what would happen
python okf_convert.py --input ./sample-input --output ./okf-bundle --dry-run
```

### 3. Sync on Changes

```bash
# After adding/editing/deleting files in the source directory:
python okf_convert.py --input ./sample-input --output ./okf-bundle --sync

# Preview before applying:
python okf_convert.py --input ./sample-input --output ./okf-bundle --sync --dry-run
```

## CLI Reference

```
usage: okf_convert.py [-h] --input INPUT --output OUTPUT
                      [--endpoint ENDPOINT] [--model MODEL]
                      [--api-key API_KEY] [--sync] [--dry-run]

Convert or sync a directory into an OKF-conformant knowledge bundle.

optional arguments:
  --input INPUT       Source directory
  --output OUTPUT     OKF bundle output directory
  --endpoint ENDPOINT LLM base URL (default: http://localhost:4000/v1)
  --model MODEL       Model for enrichment (default: gpt-4o-mini)
  --api-key API_KEY   API key (or set LITELLM_API_KEY env var)
  --sync              Incremental sync — only process new/changed files
  --dry-run           Preview without writing files
```

## How It Works

1. **Discover** — walks the input directory, picking up all supported file types
2. **Extract** — reads each file (text, code, config), parses Office docs, extracts PDF text or rasterizes scanned pages
3. **Enrich** — sends each extracted document to an LLM for automatic type classification, title, description, and tags
4. **Bundle** — writes each concept as a markdown file with YAML frontmatter, generates a root `index.md`, per-subdirectory indexes, and a timestamped `log.md`
5. **Track** — stores SHA-256 hashes in `.okf_manifest.json` so subsequent `--sync` runs only process what changed

## License

MIT
