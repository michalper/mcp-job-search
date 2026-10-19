"""render_pdf — wraps the headless-Chrome HTML-to-PDF command.

The exact invocation below is deliberately rigid: `--headless=new` combined
with `--user-data-dir` is known to hang indefinitely on first-run profile
setup, and running this in a loop across many files silently drops every PDF
after the first because later invocations collide on the same default
profile lock. Always call this once per file and check the exit code AND the
page count — a zero exit code does not guarantee a non-empty PDF.
"""

from __future__ import annotations

import re
import subprocess  # nosec B404 - fixed argv below, no shell=True, no untrusted interpolation
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import config as app_config

_TIMEOUT_S = 60

_PAGE_OBJECT = re.compile(rb"/Type\s*/Page[^s]")


def count_pdf_pages(pdf_path: Path) -> int:
    """Counts `/Type /Page` objects directly in the PDF bytes — no PDF-parsing
    dependency needed, and it works even on a PDF a viewer can't fully open."""
    try:
        return len(_PAGE_OBJECT.findall(pdf_path.read_bytes()))
    except OSError:
        return -1


@dataclass(frozen=True)
class RenderResult:
    html_path: str
    pdf_path: str
    exit_code: int
    success: bool
    page_count: int
    stderr: str | None
    reason: str | None


def render_pdf(html_path: str, pdf_path: str | None = None) -> dict[str, Any]:
    html_p = Path(html_path).expanduser().resolve()
    if not html_p.is_file():
        return asdict(
            RenderResult(
                html_path=str(html_p), pdf_path="", exit_code=-1, success=False,
                page_count=0, stderr=None, reason=f"HTML file not found: {html_p}",
            )
        )

    pdf_p = Path(pdf_path).expanduser().resolve() if pdf_path else html_p.with_suffix(".pdf")

    argv = [
        app_config.chrome_path(),
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_p}",
        f"file://{html_p}",
    ]
    try:
        proc = subprocess.run(  # nosec B603 - fixed argv, no shell, no untrusted input
            argv, capture_output=True, text=True, timeout=_TIMEOUT_S
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return asdict(
            RenderResult(
                html_path=str(html_p), pdf_path=str(pdf_p), exit_code=-1, success=False,
                page_count=0, stderr=None, reason=f"Chrome invocation failed: {exc}",
            )
        )

    if proc.returncode != 0:
        return asdict(
            RenderResult(
                html_path=str(html_p), pdf_path=str(pdf_p), exit_code=proc.returncode,
                success=False, page_count=0, stderr=proc.stderr or None,
                reason="Chrome exited non-zero",
            )
        )

    if not pdf_p.is_file():
        return asdict(
            RenderResult(
                html_path=str(html_p), pdf_path=str(pdf_p), exit_code=proc.returncode,
                success=False, page_count=0, stderr=proc.stderr or None,
                reason="exit code 0 but no PDF was written — check for a locked Chrome profile",
            )
        )

    pages = count_pdf_pages(pdf_p)
    success = pages > 0
    return asdict(
        RenderResult(
            html_path=str(html_p), pdf_path=str(pdf_p), exit_code=proc.returncode,
            success=success, page_count=pages, stderr=proc.stderr or None,
            reason=None if success else "PDF written but contains zero page objects",
        )
    )
