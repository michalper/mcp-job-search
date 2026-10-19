# mcp-job-search

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

An [MCP](https://modelcontextprotocol.io) server that automates the repetitive
mechanics around job-hunting with an AI coding assistant, while deliberately
**not** automating the parts that need a human: drafting your CV/cover letter,
fact-checking claims against your real history, and submitting an application.

> **Status: early stage.** Built for personal use, published because the
> configurable anti-fabrication linter and application-registry tooling are
> generically useful beyond one person's job search.

## What this is

Five tools:

- **`search_jobs`** — real search across job-board APIs that actually have one
  (Arbeitnow, free, no key; Adzuna and JSearch if you supply API keys).
- **`fetch_job_posting`** — turns a single job-posting URL you already found
  into structured text, for boards with no public search API.

  **Verified live, one real posting per site (2026-10-19):**

  | Site | Result |
  |---|---|
  | JustJoin.it | ✅ clean extraction |
  | NoFluffJobs | ✅ clean extraction |
  | Bulldogjob | ✅ clean extraction |
  | theprotocol.it | ✅ clean extraction |
  | Solid.Jobs | ✅ clean extraction |
  | CzyJestEldorado.pl (aggregator) | ✅ clean extraction |
  | LinkedIn (`/jobs/view/<id>`) | ✅ clean extraction — the single-posting view is public |
  | Jooble | N/A — it redirects to the source site (e.g. JustJoin.it); nothing of its own to fetch |
  | Pracuj.pl | ❌ blocked — see below |
  | Indeed (`pl.indeed.com`) | ❌ blocked — see below |

  **By design, not a bug:** Pracuj.pl and Indeed both sit behind an active
  Cloudflare bot-detection challenge — confirmed via response headers
  (`cf-mitigated: challenge` / 401 with a Cloudflare bot-management cookie,
  `server: cloudflare`), not just a missing-JS issue. This tool will never
  try to solve that challenge automatically — doing so is CAPTCHA/bot-
  detection bypass, which this project treats as off-limits regardless of
  how narrow the use case is. A real, human-driven browser session passes
  both sites' challenges normally (verified live, full content loaded) — for
  a page like this, read it with a real browser instead of this tool.
- **`render_pdf`** — renders a CV/cover-letter HTML file to PDF via headless
  Chrome, with the exact flags that avoid known hangs and silent failures.
- **`lint_cv`** — a configurable mechanical linter: banned phrases, a
  skills-section-only ban list, "lightweight achievement" overclaim patterns,
  a title check, an optional required-clause check, a body-link-style check,
  and page-count limits. Every rule comes from a YAML file you control (see
  `config/lint_rules.example.yaml`) — nothing about your own career facts is
  hardcoded into this repo.
- **`log_application`** — appends one row to a Markdown application registry
  in the right section/position, never inventing text for free-text fields.

## What this deliberately does NOT do

- **No scraping of sites without a public API.** NoFluffJobs, JustJoin.it,
  Pracuj.pl and similar boards have no documented public API; this project
  does not attempt to bypass their anti-bot protections to search them in
  bulk. `fetch_job_posting` only reads one URL you already found — the same
  as opening it in a browser yourself.
- **No auto-apply, ever.** Nothing here submits a form or sends an
  application. You always send it yourself.
- **No drafting, no fact-checking.** Writing the CV/cover-letter text, and
  verifying every claim traces back to something true, stays with whatever
  AI assistant calls these tools and has your actual career facts in context.
  This server only does the mechanical parts around that.

## Why a configurable linter, not a hardcoded one

The original motivation: a CV draft once conflated two separate true facts
into one false-sounding claim, and it shipped before anyone caught it. A
grep-based mechanical check can catch a banned phrase; it can't catch
semantic conflation — that still needs a human or an independent adversarial
review. What a mechanical linter *can* do reliably: enforce *your own*
banned-phrase list, page limits, and required clauses, consistently, every
time, without you re-checking the same things by hand. `lint_cv` is that —
generic, so anyone can point it at their own facts.

## Setup

```bash
pip install -e ".[dev]"
```

Configure via environment variables (all optional — every tool degrades
gracefully when something is unset):

| Variable | Used by | Default |
|---|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | `search_jobs` | unset — Adzuna skipped |
| `ADZUNA_COUNTRY` | `search_jobs` | `pl` |
| `RAPIDAPI_JSEARCH_KEY` | `search_jobs` | unset — JSearch skipped |
| `LINT_RULES_PATH` | `lint_cv` | bundled `config/lint_rules.example.yaml` |
| `REGISTRY_CONFIG_PATH` | `log_application` | bundled `config/registry.example.yaml` |

Add to your MCP client config (e.g. Claude Code's `.mcp.json`):

```json
{
  "mcpServers": {
    "job-search": {
      "command": "/absolute/path/to/mcp-job-search/.venv/bin/mcp-job-search",
      "env": {
        "LINT_RULES_PATH": "/absolute/path/to/your/lint_rules.yaml",
        "REGISTRY_CONFIG_PATH": "/absolute/path/to/your/registry.yaml"
      }
    }
  }
}
```

## Development

```bash
pytest -q
ruff check .
mypy src
bandit -c pyproject.toml -r src
pip-audit
```

One manual end-to-end check (not run in CI — needs live network and a real
Chrome install):

1. `search_jobs(keywords="PHP", remote_only=True, sources=["arbeitnow"])` against
   the live Arbeitnow API.
2. `fetch_job_posting(url=...)` on a URL from step 1.
3. `render_pdf(html_path=...)` on a sample CV, confirm `success` and `page_count`.
4. `lint_cv(html_path=...)` on a file with a seeded violation, confirm it's reported.
5. `log_application(..., dry_run=True)` against your own registry, confirm the
   previewed row and insertion point look right before dropping `dry_run`.

## License

MIT — see [LICENSE](LICENSE).
