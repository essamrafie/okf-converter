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
import sys
import json
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

mcp = FastMCP("okf-converter", port=8006)


# ── Helper ────────────────────────────────────────────────────────
def _resolve_path(path_str: str) -> str:
    """Resolve ~ and return absolute path string."""
    return str(Path(path_str).expanduser().resolve())


# ── Tools ─────────────────────────────────────────────────────────

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
) -> str:
    """Incrementally sync an existing OKF bundle with source directory changes.

    Only processes new, modified, or deleted files since the last conversion.

    Args:
        input_dir: Path to the source directory.
        output_dir: Path to the existing OKF bundle directory.
        llm_endpoint: OpenAI-compatible LLM endpoint for enrichment.
        llm_model: Model name for enrichment.
        api_key: API key for the LLM endpoint.
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


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OKF Converter MCP Server")
    parser.add_argument("mode", nargs="?", default="stdio",
                        choices=["stdio", "sse"],
                        help="Transport mode (default: stdio)")
    args = parser.parse_args()

    if args.mode == "sse":
        print("Starting OKF MCP server on SSE (port 8006)...", file=sys.stderr)
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
