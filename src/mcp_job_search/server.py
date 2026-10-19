"""MCP server — job search, posting fetch, CV PDF rendering, configurable
anti-fabrication linting, and application-registry logging.

Drafting the CV/cover-letter text itself, and adversarially fact-checking it
against your own career facts, are explicitly OUT of scope here — that stays
in whatever AI coding assistant calls these tools, using its own context
(your resume source-of-truth file, your own review process). This server is
a data/mechanics layer: it finds postings, renders PDFs, flags mechanical
red flags, and logs outcomes — it never submits an application on your
behalf.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .applications import log_application as _log_application
from .fetch_posting import fetch_job_posting as _fetch_job_posting
from .lint import lint_cv as _lint_cv
from .pdf import render_pdf as _render_pdf
from .search import search_jobs as _search_jobs

try:
    _VERSION = version("mcp-job-search")
except PackageNotFoundError:
    _VERSION = ""

server = MCPServer(
    name="mcp-job-search",
    version=_VERSION,
    instructions=(
        "Job-search mechanics for an AI coding/writing assistant: search real "
        "job-board APIs, fetch a single posting's text from a URL you already "
        "found, render a CV/cover-letter HTML file to PDF, lint HTML against "
        "your own configurable rule set, and log an outcome to your "
        "application registry. Never submits anything — the human always "
        "sends the application."
    ),
)


@server.tool(
    description=(
        "Searches real job-board APIs (Arbeitnow — free, always on; Adzuna and "
        "JSearch — only if their API keys are configured via environment "
        "variables). Returns normalized jobs plus a list of source errors "
        "(e.g. a source skipped because its key isn't set) — never raises on "
        "a single source's failure. Results are cached by query for "
        "SEARCH_CACHE_TTL_SECONDS (default 6h) to protect JSearch's free "
        "quota; pass use_cache=False to force a fresh query. This does NOT scrape or search sites "
        "without a public API (e.g. NoFluffJobs, JustJoin.it, Pracuj.pl) — "
        "use fetch_job_posting for a specific URL on those instead."
    )
)
def search_jobs(
    keywords: Annotated[
        str, Field(description="Keywords to match, e.g. 'PHP Magento backend'.")
    ],
    location: Annotated[
        str | None, Field(description="Free-text location filter, e.g. 'Poland'.")
    ] = None,
    remote_only: Annotated[bool, Field(description="Only return remote-flagged postings.")] = False,
    sources: Annotated[
        list[str] | None,
        Field(description="Limit to these source names, e.g. ['arbeitnow']. Default: all."),
    ] = None,
    use_cache: Annotated[
        bool, Field(description="Reuse a cached result. False forces a fresh query.")
    ] = True,
) -> dict[str, Any]:
    return _search_jobs(
        keywords=keywords, location=location, remote_only=remote_only,
        sources=sources, use_cache=use_cache,
    )


@server.tool(
    description=(
        "Fetches ONE job-posting URL you already found (any job board, "
        "including ones with no public API) and extracts its readable text "
        "generically. This is for a single posting a human found manually — "
        "never call it in a loop to enumerate a site's listings."
    )
)
def fetch_job_posting(
    url: Annotated[str, Field(description="A single job-posting URL.")],
) -> dict[str, Any]:
    return _fetch_job_posting(url)


@server.tool(
    description=(
        "Renders one CV/cover-letter HTML file to PDF via headless Chrome, "
        "using the exact flags known not to hang or silently drop output. "
        "Checks both the exit code and the actual PDF page count — call this "
        "once per file, never in a batch loop on the same Chrome profile."
    )
)
def render_pdf(
    html_path: Annotated[str, Field(description="Path to the source HTML file.")],
    pdf_path: Annotated[
        str | None, Field(description="Output PDF path; defaults to the HTML path with .pdf.")
    ] = None,
) -> dict[str, Any]:
    return _render_pdf(html_path=html_path, pdf_path=pdf_path)


@server.tool(
    description=(
        "Read-only — never modifies html_path, pdf_path, or any other file. "
        "Lints a CV/cover-letter HTML file against YOUR OWN configurable "
        "rule set (banned phrases, skills-section bans, achievement-weight "
        "overclaims, title/GDPR/link checks, page-count limits), read from "
        "LINT_RULES_PATH (an env var, not a parameter here; defaults to a "
        "bundled generic example). Mechanical matching only — cannot catch "
        "semantic fabrication (two true facts combined into a false-sounding "
        "one), which still needs a human or independent review. Call before "
        "render_pdf while iterating on a draft (cheap, no Chrome, HTML-only "
        "checks); call again after render_pdf with pdf_path to also check "
        "page count and staleness — render_pdf itself runs none of this."
    )
)
def lint_cv(
    html_path: Annotated[
        str, Field(description="Path to the HTML file to lint, as currently saved on disk.")
    ],
    pdf_path: Annotated[
        str | None,
        Field(
            description=(
                "Optional. Omit to run only the HTML-based checks (content, skills, "
                "weight, title, links). Pass the already-rendered PDF's path to ALSO "
                "check its page count against your configured page_limits and confirm "
                "it isn't older than html_path — this tool never renders a PDF itself; "
                "call render_pdf first if pdf_path doesn't exist yet."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    return _lint_cv(html_path=html_path, pdf_path=pdf_path)


@server.tool(
    description=(
        "Appends one row to your application registry (a Markdown file with "
        "one '## <portal>' heading per job board, each holding a table). "
        "Target file and column layout come from REGISTRY_CONFIG_PATH "
        "(default: the bundled generic example). Never invents text for "
        "free-text fields — only places exactly what you pass. Use dry_run "
        "to preview the row and insertion point without writing."
    )
)
def log_application(
    portal: Annotated[str, Field(description="Section heading to log under, e.g. 'justjoin.it'.")],
    date: Annotated[str, Field(description="ISO date (YYYY-MM-DD) of the application.")],
    company: Annotated[str, Field(description="Company name.")],
    role: Annotated[str, Field(description="Role/title applied for.")],
    rate: Annotated[str | None, Field(description="Rate/salary as free text.")] = None,
    mode: Annotated[str | None, Field(description="Work mode, e.g. 'Remote'.")] = None,
    level: Annotated[
        str | None, Field(description="Seniority/contract level, e.g. 'Senior B2B'.")
    ] = None,
    status_note: Annotated[
        str | None, Field(description="Free-text status/notes — placed verbatim.")
    ] = None,
    dry_run: Annotated[bool, Field(description="Preview without writing to the file.")] = False,
) -> dict[str, Any]:
    return _log_application(
        portal=portal, date_=date, company=company, role=role, rate=rate,
        mode=mode, level=level, status_note=status_note, dry_run=dry_run,
    )


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
