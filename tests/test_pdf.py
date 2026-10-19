from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_job_search.pdf import count_pdf_pages, render_pdf


def test_count_pdf_pages_from_minimal_bytes(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "fake.pdf"
    # two page objects, hand-built — enough to exercise the byte regex without a real PDF
    fake_pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n"
    )
    assert count_pdf_pages(fake_pdf) == 2


def test_count_pdf_pages_missing_file(tmp_path: Path) -> None:
    assert count_pdf_pages(tmp_path / "missing.pdf") == -1


def test_render_pdf_missing_html(tmp_path: Path) -> None:
    result = render_pdf(str(tmp_path / "missing.html"))
    assert result["success"] is False
    assert "not found" in result["reason"]


def test_render_pdf_success(tmp_path: Path) -> None:
    html = tmp_path / "cv.html"
    html.write_text("<html><body>hi</body></html>")
    pdf_path = tmp_path / "cv.pdf"

    def _fake_run(argv, **kwargs):
        pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n")
        return subprocess.CompletedProcess(argv, returncode=0, stdout="", stderr="")

    with patch("mcp_job_search.pdf.subprocess.run", side_effect=_fake_run):
        result = render_pdf(str(html), str(pdf_path))

    assert result["success"] is True
    assert result["page_count"] == 1
    assert result["exit_code"] == 0


def test_render_pdf_nonzero_exit(tmp_path: Path) -> None:
    html = tmp_path / "cv.html"
    html.write_text("<html></html>")

    fake_proc = MagicMock(returncode=1, stdout="", stderr="chrome crashed")
    with patch("mcp_job_search.pdf.subprocess.run", return_value=fake_proc):
        result = render_pdf(str(html))

    assert result["success"] is False
    assert result["exit_code"] == 1
    assert result["stderr"] == "chrome crashed"


def test_render_pdf_exit_zero_but_no_file(tmp_path: Path) -> None:
    html = tmp_path / "cv.html"
    html.write_text("<html></html>")

    fake_proc = MagicMock(returncode=0, stdout="", stderr="")
    with patch("mcp_job_search.pdf.subprocess.run", return_value=fake_proc):
        result = render_pdf(str(html), str(tmp_path / "never_written.pdf"))

    assert result["success"] is False
    assert "no PDF was written" in result["reason"]
