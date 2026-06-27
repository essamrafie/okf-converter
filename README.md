# OKF Converter

Convert any directory of documents, code, and data into an **OKF-conformant knowledge bundle** — searchable, LLM-enriched markdown concepts that you can query and sync incrementally.

**OKF** (Open Knowledge Format) is [Google Cloud's open specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) for portable, cross-linked knowledge that humans and AI agents can read. No database, no runtime — just directories of `.md` files.

---

## Features

- **Multi-format** — PDF, DOCX, PPTX, XLSX, CSV, images (OCR via Tesseract), code, configs
- **LLM enrichment** — auto-generates `type`, `title`, `description`, `tags` via any OpenAI-compatible API (DeepSeek, OpenAI, Ollama, LiteLLM)
- **Incremental sync** — `--sync` mirrors your source directory: add files → add concepts, remove files → remove concepts
- **OCR** — image-only documents (screenshots in docx) are OCR'd with Tesseract
- **MCP server** — expose OKF tools to Open Web UI, Claude Desktop, Cursor
- **Portable** — plain markdown, git-friendly, no database

---

## Step-by-Step Installation

### 1. Clone

```bash
git clone https://github.com/essamrafie/okf-converter.git
cd okf-converter
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) Install Office & PDF Parsers

For DOCX, PPTX, XLSX, PDF, CSV support:

```bash
pip install python-docx python-pptx openpyxl pandas PyMuPDF xlrd tabulate
```

### 5. (Optional) Install OCR

For extracting text from images inside documents:

```bash
brew install tesseract
pip install pytesseract Pillow
```

### 6. Set Up API Key

Save your DeepSeek (or other LLM) API key — the converter picks it up automatically:

```bash
echo "sk-your-api-key-here" > ~/deepseek_api
```

Or set it as an environment variable:

```bash
export DEEPSEEK_API_KEY="sk-your-api-key-here"
```

---

## Usage

### Convert a Directory

```bash
python okf_convert.py --input ./sample-input --output ./okf-bundle \
    --endpoint https://api.deepseek.com/v1 --model deepseek-chat
```

### Sync After Changes

```bash
# Add or remove files from ./sample-input, then:
python okf_convert.py --input ./sample-input --output ./okf-bundle --sync
```

### Preview Without Writing

```bash
python okf_convert.py --input ./sample-input --output ./okf-bundle --dry-run
```

---

## CLI Reference

```
usage: okf_convert.py --input INPUT --output OUTPUT [options]

required:
  --input INPUT       Source directory
  --output OUTPUT     OKF bundle output path

LLM enrichment:
  --endpoint URL      OpenAI-compatible base URL (default: http://localhost:4000/v1)
  --model NAME        Model for type/title/description/tags (default: gpt-4o-mini)
  --api-key KEY       API key (auto-reads from ~/deepseek_api, DEEPSEEK_API_KEY, or LITELLM_API_KEY)

modes:
  --sync              Incremental sync — add, update, and delete concepts to mirror source
  --dry-run           Preview without writing anything
```

---

## MCP Server

Expose OKF tools to AI agents via the [Model Context Protocol](https://modelcontextprotocol.io).

### Run the Server

```bash
source .venv/bin/activate

# For Open Web UI (Streamable HTTP on port 8006):
python mcp_server.py sse
```

### Available Tools

| Tool | Description |
|------|-------------|
| `okf_preview` | Scan a directory and list supported files by type |
| `okf_read` | Extract text from any file (with OCR fallback for images) |
| `okf_search` | Search for text across all source files |
| `okf_read_concept` | Find and read a concept by name from an OKF bundle |
| `okf_search_bundle` | Search text inside all concept markdown files |
| `okf_list_bundle` | List all concepts in a bundle |
| `okf_convert` | Full conversion — every file becomes an OKF concept |
| `okf_sync` | Incremental sync — only new/changed/deleted files |
| `okf_dry_run` | Preview without writing anything |

### Connect to Open Web UI

1. Run the server: `python mcp_server.py sse`
2. In Open Web UI go to **⚙️ Admin Settings → External Tools → + Add Server**
3. Set:
   - **Type**: `MCP (Streamable HTTP)`
   - **URL**: `http://host.docker.internal:8006/mcp` (Docker) or `http://10.55.68.4:8006/mcp` (LAN)
4. Save

The server reads your API key from `~/deepseek_api` automatically.

### Run as a Service (macOS)

To keep the server running on boot with auto-restart:

```bash
launchctl load ~/Library/LaunchAgents/com.essam.okf-converter-mcp.plist
```

To stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.essam.okf-converter-mcp.plist
```

Logs: `~/dev/okf-converter/mcp-server.log`

---

## Supported Formats

| Type | Extensions | Extraction Method |
|------|-----------|-------------------|
| **Text** | `.md` `.txt` `.rst` `.py` `.js` `.ts` `.sh` `.yaml` `.yml` `.json` `.toml` `.cfg` `.ini` `.env` | Direct read |
| **Office** | `.docx` `.pptx` `.xlsx` `.xls` `.xlsm` | python-docx, python-pptx, openpyxl |
| **Spreadsheets** | `.csv` `.tsv` | Pandas |
| **PDF** | `.pdf` | PyMuPDF (text + scanned page rasterization) |
| **OCR** | Image-only docx/pptx | Tesseract |

---

## Pipeline

1. **Discover** — walks input directory (skips `.git`, `node_modules`, `__pycache__`, `.venv`)
2. **Extract** — reads text, parses Office/PDF, OCRs images if no text found
3. **Enrich** — sends extracted content to an LLM for `{type, title, description, tags}`
4. **Bundle** — writes each concept as an OKF `.md` with YAML frontmatter, `index.md`, `log.md`
5. **Track** — SHA-256 manifest in `.okf_manifest.json` for incremental sync

---

## How OKF Conformance Works

### Bundle Structure
```
okf-bundle/
├── index.md              ← root listing (okf_version: "0.1" in frontmatter)
├── log.md                ← change history
├── <concept>.md          ← concepts at root
└── <subdirectory>/
    ├── index.md          ← per-directory listing
    └── <concept>.md
```

### Concept Format

```markdown
---
type: Code Module
title: Greeting Service
description: A demo greeting module
tags: [demo, python]
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

### OKF Rules (automatically satisfied)
- **M1** — Bundle is a directory of `.md` concept files ✓
- **M2** — Every concept starts with YAML frontmatter ✓
- **M3** — Frontmatter has non-empty `type` field ✓
- **M6** — No runtime/database needed ✓

---

## Links

| Resource | URL |
|----------|-----|
| **OKF Spec (Google Cloud)** | https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md |
| **Google Cloud Blog** | https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing |
| **OKF Conformance Suite** | https://github.com/Sudhakaran88/okf-conformance |
| **OKF Toolkit** | https://github.com/akdira/okf-toolkit |

## License

MIT
