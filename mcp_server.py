#!/usr/bin/env python3
"""
MCP Server for OKF Converter.
Exposes convert and sync as tools consumable by Open Web UI, Claude Desktop, etc.

Run with SSE transport (for Open Web UI):
    python mcp_server.py sse

Run with stdio transport (for Claude Desktop / CLI clients):
    python mcp_server.py
"""

import argparse
import os
import re
import sys
import json
import yaml
from pathlib import Path

# Ensure the project root is on sys.path so we can import okf_convert
_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(_root))

from okf_convert import (
    convert as _convert,
    sync as _sync,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
)
from okf_convert import collect_files  # for preview counts


# ── MCP Server Setup ──────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("MCP SDK required. Install: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Auto-read DeepSeek API key from ~/deepseek_api
_api_key_path = Path("~/deepseek_api").expanduser()
_DEFAULT_API_KEY = (
    os.environ.get("LITELLM_API_KEY")
    or os.environ.get("DEEPSEEK_API_KEY")
    or (_api_key_path.read_text(encoding="utf-8").strip() if _api_key_path.exists() else "")
)

mcp = FastMCP("okf-converter", host="0.0.0.0", port=8006)


# ── Helper ────────────────────────────────────────────────────────
def _resolve_path(path_str: str) -> str:
    """Resolve ~ and return absolute path string."""
    return str(Path(path_str).expanduser().resolve())


# ── Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def okf_read(input_file: str) -> str:
    """Extract and return the full text content of a file (docx, pdf, code, etc.).

    Args:
        input_file: Absolute path to the file to read.
    """
    from okf_convert import extract_text

    fp = Path(_resolve_path(input_file))
    if not fp.is_file():
        return json.dumps({"error": f"File not found: {fp}"})

    try:
        content, note = extract_text(fp)
        return json.dumps({
            "file": str(fp),
            "extraction": note,
            "chars": len(content),
            "content": content,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def okf_search(input_dir: str, query: str) -> str:
    """Search for text across all supported files in a directory.

    Args:
        input_dir: Path to the source directory.
        query: Text or regex pattern to search for (case-insensitive).
    """
    import re

    src = Path(_resolve_path(input_dir))
    if not src.is_dir():
        return json.dumps({"error": f"Directory not found: {src}"})

    from okf_convert import collect_files, extract_text

    files = collect_files(src)
    results = []
    for fp in files:
        try:
            content, _ = extract_text(fp)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if re.search(query, line, re.IGNORECASE):
                    results.append({
                        "file": str(fp.relative_to(src)),
                        "line": i,
                        "match": line.strip()[:200],
                    })
        except Exception:
            pass

    return json.dumps({
        "query": query,
        "matches": len(results),
        "results": results[:50],
    }, indent=2)


@mcp.tool()
def okf_read_concept(bundle_dir: str, concept_name: str) -> str:
    """Find and read a concept by name from an OKF bundle.

    Searches the bundle for any concept whose filename or title matches the given name.
    Returns the full frontmatter + body of the matching concept.

    Args:
        bundle_dir: Path to the OKF bundle directory. Relative paths like 'okf-bundle' are resolved under the project home.
        concept_name: Name or partial name of the concept to find (e.g. 'quick wins', 'integration plan').
    """
    bd = Path(_resolve_path(bundle_dir))

    # If not found, try common locations
    if not bd.is_dir():
        alt = Path.home() / "dev" / "okf-converter" / bundle_dir
        if alt.is_dir():
            bd = alt

    if not bd.is_dir():
        return json.dumps({"error": f"Bundle directory not found: {bd}"})

    from okf_convert import RESERVED_FILENAMES
    import yaml

    query = concept_name.lower()
    matches = []

    for md in sorted(bd.rglob("*.md")):
        if md.stem.lower() in RESERVED_FILENAMES:
            continue
        if md.parent.name.startswith("."):
            continue

        raw = md.read_text(encoding="utf-8", errors="replace")
        title = md.stem
        desc = ""

        if raw.startswith("---"):
            try:
                end = raw.index("---", 3)
                fm = yaml.safe_load(raw[3:end])
                title = fm.get("title", md.stem)
                desc = fm.get("description", "")
            except Exception:
                pass

        if query in title.lower() or query in desc.lower() or query in md.stem.lower():
            matches.append({
                "path": str(md.relative_to(bd)),
                "title": title,
                "description": desc,
                "content": raw,
            })

    return json.dumps({
        "concept_name": concept_name,
        "matches_found": len(matches),
        "matches": matches,
    }, indent=2)


@mcp.tool()
def okf_search_bundle(bundle_dir: str, query: str) -> str:
    """Search for text inside all concept markdown files in an OKF bundle.

    Searches the full content (frontmatter + body) of every concept.

    Args:
        bundle_dir: Path to the OKF bundle directory.
        query: Text to search for (case-insensitive).
    """
    import re

    bd = Path(_resolve_path(bundle_dir))

    # If not found, try common locations
    if not bd.is_dir():
        alt = Path.home() / "dev" / "okf-converter" / bundle_dir
        if alt.is_dir():
            bd = alt

    if not bd.is_dir():
        return json.dumps({"error": f"Bundle directory not found: {bd}"})

    from okf_convert import RESERVED_FILENAMES

    results = []
    for md in sorted(bd.rglob("*.md")):
        if md.stem.lower() in RESERVED_FILENAMES:
            continue
        if md.parent.name.startswith("."):
            continue

        raw = md.read_text(encoding="utf-8", errors="replace")
        lines = raw.split("\n")
        for i, line in enumerate(lines, 1):
            if re.search(query, line, re.IGNORECASE):
                results.append({
                    "file": str(md.relative_to(bd)),
                    "line": i,
                    "match": line.strip()[:200],
                })

    return json.dumps({
        "query": query,
        "matches": len(results),
        "results": results[:50],
    }, indent=2)


@mcp.tool()
def okf_preview(input_dir: str) -> str:
    """Preview a directory — count supported files by type without converting.

    Args:
        input_dir: Path to the source directory to scan.
    """
    src = Path(_resolve_path(input_dir))
    if not src.is_dir():
        return json.dumps({"error": f"Directory not found: {src}"})

    from okf_convert import TEXT_EXTENSIONS, OFFICE_EXTENSIONS, PDF_EXTENSIONS

    files = collect_files(src)
    text_count = sum(1 for f in files if f.suffix.lower() in TEXT_EXTENSIONS)
    office_count = sum(1 for f in files if f.suffix.lower() in OFFICE_EXTENSIONS)
    pdf_count = sum(1 for f in files if f.suffix.lower() in PDF_EXTENSIONS)

    return json.dumps({
        "input_dir": str(src),
        "total_files": len(files),
        "text": text_count,
        "office": office_count,
        "pdf": pdf_count,
        "files": [str(f.relative_to(src)) for f in files],
    }, indent=2)


@mcp.tool()
def okf_convert(
    input_dir: str,
    output_dir: str,
    llm_endpoint: str = DEFAULT_ENDPOINT,
    llm_model: str = DEFAULT_MODEL,
    api_key: str = "",
) -> str:
    """Convert a directory of files into an OKF-conformant knowledge bundle.

    Args:
        input_dir: Path to the source directory containing documents to convert.
        output_dir: Path where the OKF bundle will be written.
        llm_endpoint: OpenAI-compatible LLM endpoint for enrichment (e.g. https://api.deepseek.com/v1).
        llm_model: Model name for enrichment (e.g. deepseek-chat, gpt-4o-mini).
        api_key: API key for the LLM endpoint. Falls back to LITELLM_API_KEY, DEEPSEEK_API_KEY env vars, or ~/deepseek_api file.
    """
    src = Path(_resolve_path(input_dir))
    out = Path(_resolve_path(output_dir))

    if not src.is_dir():
        return json.dumps({"error": f"Input directory not found: {src}"})

    key = api_key or _DEFAULT_API_KEY

    # Capture stdout from the converter
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            _convert(
                source_dir=src,
                output_dir=out,
                endpoint=llm_endpoint,
                model=llm_model,
                api_key=key,
                dry_run=False,
            )
        return buf.getvalue()
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def okf_sync(
    input_dir: str,
    output_dir: str,
    llm_endpoint: str = DEFAULT_ENDPOINT,
    llm_model: str = DEFAULT_MODEL,
    api_key: str = "",
    prune: bool = False,
) -> str:
    """Incrementally sync an existing OKF bundle with source directory changes.

    Only processes new, modified, or deleted files since the last conversion.
    By default, deleted source files keep their concepts in the bundle.
    Set prune=True to also remove concepts for deleted source files.

    Args:
        input_dir: Path to the source directory.
        output_dir: Path to the existing OKF bundle directory.
        llm_endpoint: OpenAI-compatible LLM endpoint for enrichment.
        llm_model: Model name for enrichment.
        api_key: API key for the LLM endpoint.
        prune: If true, remove concepts for deleted source files.
    """
    src = Path(_resolve_path(input_dir))
    out = Path(_resolve_path(output_dir))

    if not src.is_dir():
        return json.dumps({"error": f"Input directory not found: {src}"})
    if not out.is_dir():
        return json.dumps({"error": f"Output directory not found — run okf_convert first: {out}"})

    key = api_key or _DEFAULT_API_KEY

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            _sync(
                source_dir=src,
                output_dir=out,
                endpoint=llm_endpoint,
                model=llm_model,
                api_key=key,
                dry_run=False,
                prune=prune,
            )
        return buf.getvalue()
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def okf_dry_run(
    input_dir: str,
    output_dir: str,
    llm_endpoint: str = DEFAULT_ENDPOINT,
    llm_model: str = DEFAULT_MODEL,
) -> str:
    """Preview what a conversion would do without writing any files.

    Args:
        input_dir: Path to the source directory.
        output_dir: Path where the bundle would be written.
        llm_endpoint: LLM endpoint for enrichment.
        llm_model: Model name for enrichment.
    """
    src = Path(_resolve_path(input_dir))
    out = Path(_resolve_path(output_dir))

    if not src.is_dir():
        return json.dumps({"error": f"Input directory not found: {src}"})

    key = _DEFAULT_API_KEY

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            _convert(
                source_dir=src,
                output_dir=out,
                endpoint=llm_endpoint,
                model=llm_model,
                api_key=key,
                dry_run=True,
            )
        return buf.getvalue()
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Bundle Query Tools ────────────────────────────────────────────

@mcp.tool()
def okf_list_bundle(bundle_dir: str) -> str:
    """List all concepts in an existing OKF bundle — read the bundle index.

    Args:
        bundle_dir: Path to the OKF bundle directory.
    """
    src = Path(_resolve_path(bundle_dir))
    if not src.is_dir():
        return json.dumps({"error": f"Bundle directory not found: {src}"})

    index = src / "index.md"
    if not index.is_file():
        return json.dumps({"error": "No index.md found — not an OKF bundle"})

    content = index.read_text(encoding="utf-8")
    # Parse concepts from the index markdown
    concepts = []
    for line in content.split("\n"):
        m = re.match(r"- \[(.+?)\]\((.+?)\)", line)
        if m:
            concepts.append({"title": m.group(1), "path": m.group(2)})

    # Also scan for subdirectory indexes
    subdirs = {}
    for idx in sorted(src.rglob("*/index.md")):
        rel = idx.relative_to(src)
        if str(rel) != "index.md":
            subdirs[str(rel.parent)] = idx

    return json.dumps({
        "bundle": str(src),
        "total_concepts": len(concepts),
        "concepts": concepts,
        "subdirectories": list(subdirs.keys()),
    }, indent=2)


@mcp.tool()
def okf_get_concept(bundle_dir: str, concept_path: str) -> str:
    """Retrieve the full content of a concept file from an OKF bundle.

    Args:
        bundle_dir: Path to the OKF bundle directory.
        concept_path: Relative path to the concept .md file (e.g. 'docs/dubai-crude-analysis.md').
    """
    src = Path(_resolve_path(bundle_dir))
    if not src.is_dir():
        return json.dumps({"error": f"Bundle directory not found: {src}"})

    fp = src / concept_path.lstrip("/")
    if not fp.is_file():
        return json.dumps({"error": f"Concept not found: {concept_path}"})

    if fp.suffix != ".md":
        return json.dumps({"error": "Not a concept file — bundle concepts are .md files"})

    raw = fp.read_text(encoding="utf-8")

    # Parse frontmatter
    fm = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end > 0:
            try:
                fm = yaml.safe_load(raw[3:end])
            except Exception:
                fm = {}
            body = raw[end + 3:].strip()

    return json.dumps({
        "file": concept_path,
        "frontmatter": fm,
        "body_chars": len(body),
        "body": body,
    }, indent=2)


@mcp.tool()
def okf_search_bundle(bundle_dir: str, query: str) -> str:
    """Search across all concept files in an OKF bundle.

    Searches both frontmatter (title, type, tags, description) and body content.

    Args:
        bundle_dir: Path to the OKF bundle directory.
        query: Text or regex pattern to search for (case-insensitive).
    """
    import re as _re

    src = Path(_resolve_path(bundle_dir))
    if not src.is_dir():
        return json.dumps({"error": f"Bundle directory not found: {src}"})

    from okf_convert import RESERVED_FILENAMES

    results = []
    for md_path in sorted(src.rglob("*.md")):
        rel = md_path.relative_to(src)
        # Skip reserved files (index, log, manifest)
        if rel.parts[0].startswith("."):
            continue
        if md_path.stem.lower() in RESERVED_FILENAMES:
            continue

        raw = md_path.read_text(encoding="utf-8")

        # Parse frontmatter for metadata search
        fm_text = ""
        body = raw
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end > 0:
                fm_text = raw[3:end]
                body = raw[end + 3:].strip()

        # Search frontmatter
        fm_matches = []
        for i, line in enumerate(fm_text.split("\n"), 1):
            if _re.search(query, line, _re.IGNORECASE):
                fm_matches.append({"line": i, "match": line.strip()[:200]})

        # Search body
        body_matches = []
        for i, line in enumerate(body.split("\n"), 1):
            if _re.search(query, line, _re.IGNORECASE):
                body_matches.append({"line": i, "match": line.strip()[:200]})

        if fm_matches or body_matches:
            results.append({
                "concept": str(rel),
                "frontmatter_matches": len(fm_matches),
                "body_matches": len(body_matches),
                "snippet": body_matches[0]["match"] if body_matches else fm_matches[0]["match"],
            })

    return json.dumps({
        "query": query,
        "matches": len(results),
        "results": results[:30],
    }, indent=2)


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OKF Converter MCP Server")
    parser.add_argument("mode", nargs="?", default="stdio",
                        choices=["stdio", "sse"],
                        help="Transport mode (default: stdio)")
    args = parser.parse_args()

    if args.mode == "sse":
        print("Starting OKF MCP server on Streamable HTTP (0.0.0.0:8006)...", file=sys.stderr)
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
