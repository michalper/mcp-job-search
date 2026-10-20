# mcp-job-search

<!-- mcp-name: io.github.michalper/mcp-job-search -->

[![CI](https://github.com/michalper/mcp-job-search/actions/workflows/ci.yml/badge.svg)](https://github.com/michalper/mcp-job-search/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-job-search-mp.svg)](https://pypi.org/project/mcp-job-search-mp/)
[![michalper/mcp-job-search MCP server](https://glama.ai/mcp/servers/michalper/mcp-job-search/badges/score.svg)](https://glama.ai/mcp/servers/michalper/mcp-job-search)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Last commit](https://img.shields.io/github/last-commit/michalper/mcp-job-search)](https://github.com/michalper/mcp-job-search/commits/main)

An [MCP](https://modelcontextprotocol.io) server that automates the repetitive
mechanics around job-hunting with an AI coding assistant, while deliberately
**not** automating the parts that need a human: drafting your CV/cover letter,
fact-checking claims against your real history, and submitting an application.

It answers the question that keeps eating a job search's time: *"this CV
draft looks fine, but did it quietly fabricate something, and is this one
specific posting even worth reading?"*

> **Status: early stage.** Built for personal use, published because the
> configurable anti-fabrication linter and application-registry tooling are
> generically useful beyond one person's job search. All seven tools are
> working. See `CHANGELOG.md` for what changed and what was verified live.

## How this differs from other job-search MCP servers

A few open-source MCP servers already do job search + CV tailoring
(`not-boring-resume-mcp`, `resume-mcp`, `Workopia MCP`, `IAM MCP Server`,
`LinkedIn MCP Server`, among others). This one targets what they don't:

1. **It won't scrape past a bot-detection wall, even quietly.** NoFluffJobs,
   JustJoin.it and similar Polish IT boards have no public search API —
   `fetch_job_posting` reads one URL you already found instead of indexing
   their listings, and on boards confirmed to sit behind an active
   Cloudflare challenge (Pracuj.pl, Indeed), it fails loudly rather than
   trying to solve the challenge automatically. See the verified coverage
   table below — this is a documented boundary, not a silent gap.
2. **The anti-fabrication linter is a configurable rules engine, not
   hardcoded prose.** None of the surveyed alternatives ship a way to
   enforce *your own* banned-phrase list, achievement-weight rules, or
   required clauses — `lint_cv` reads them from a YAML file you control, so
   the mechanism is reusable even though the facts it checks against are
   personal (see "Why a configurable linter" below).
3. **It doesn't draft or fact-check for you, on purpose.** Writing the
   CV/cover-letter text and adversarially verifying every claim traces back
   to something true stays with whatever AI assistant calls these tools —
   this server is a mechanics layer (search, fetch, render, lint, log), not
   a weaker bundled LLM call duplicating judgment the calling assistant
   already does better with full context.

**What this server doesn't pretend to be:** it doesn't cover every job
board — only ones with a real API, or a single posting URL a human already
found. It never submits anything on your behalf. And a clean `lint_cv` run
doesn't mean a CV is honest, only that it passes the specific rules you
wrote — semantic fabrication (two true facts combined into a false-sounding
one) still needs a human or an independent adversarial review to catch.

## Install

From PyPI (published as `mcp-job-search-mp` — `mcp-job-search` was already
taken by an unrelated project; the command stays `mcp-job-search`):

```bash
pip install mcp-job-search-mp
# or, for an isolated tool install:
uvx mcp-job-search-mp
```

From source, for development:

```bash
git clone https://github.com/michalper/mcp-job-search.git
cd mcp-job-search
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Connecting to Claude Code

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

Configure via environment variables — all optional, every tool degrades
gracefully when something is unset:

| Variable | Used by | Default |
|---|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | `search_jobs` | unset — Adzuna skipped |
| `ADZUNA_COUNTRY` | `search_jobs` | `pl` |
| `RAPIDAPI_JSEARCH_KEY` | `search_jobs` | unset — JSearch skipped |
| `JSEARCH_COUNTRY` | `search_jobs` | `us` (JSearch's own API default) |
| `LINT_RULES_PATH` | `lint_cv` | bundled `src/mcp_job_search/examples/lint_rules.example.yaml` |
| `REGISTRY_CONFIG_PATH` | `log_application` | bundled `src/mcp_job_search/examples/registry.example.yaml` |
| `CHROME_PATH` | `render_pdf` | auto-detected (macOS app bundle, Linux `$PATH`, common Windows install dirs) |
| `SEARCH_CACHE_DIR` | `search_jobs` | `~/.cache/mcp-job-search/search` |
| `SEARCH_CACHE_TTL_SECONDS` | `search_jobs` | `21600` (6 hours) |

### Adzuna and JSearch free-tier limits

Adzuna's free tier is 25 one-time test calls, then a paid plan (£8/month,
5,000 calls) — budget calls accordingly once past testing. JSearch's free
tier is 200 requests/month; `search_jobs` caches results by query
(`SEARCH_CACHE_DIR`/`SEARCH_CACHE_TTL_SECONDS`, default 6h) specifically to
protect that quota from repeated identical queries — pass `use_cache=False`
to force a fresh one when you actually need it.

### Sites behind active bot-detection

`fetch_job_posting` will never try to solve a CAPTCHA or bot-detection
challenge automatically, on any site, regardless of how narrow the request
— confirmed via response headers that Pracuj.pl and Indeed (`pl.indeed.com`)
both sit behind an active Cloudflare challenge (`cf-mitigated: challenge` /
401 with a Cloudflare bot-management cookie), not just a missing-JavaScript
issue. A real, human-driven browser session passes both normally — for a
page like this, read it with a real browser instead of this tool.

## Example: catching a CV the way `lint_cv` sees it

![lint_cv running against a seeded CV draft and reporting seven findings: corporate jargon, an unsupported superlative, an unproven cloud claim, a .gitignore edit and a commit count stated as achievements, a title contradicting the real specialization, and a link that should be plain text](docs/assets/demo.gif)

The CV draft here (`tests/fixtures/sample_cv_with_violations.html`) was
seeded on purpose, and `lint_cv` is pointed at the bundled generic example
rules (`src/mcp_job_search/examples/lint_rules.example.yaml`), not a real person's facts:

```json
{
  "clean": false,
  "findings": [
    {"severity": "error", "message": "generic corporate jargon — replace with a concrete claim"},
    {"severity": "error", "message": "unsupported superlative — ground it in a specific result or cut it"},
    {"severity": "error", "message": "example: list cloud/K8s here only if you have real production experience"},
    {"severity": "error", "message": "a .gitignore edit is hygiene, not an achievement"},
    {"severity": "error", "message": "a commit count is not an achievement on its own"},
    {"severity": "error", "message": "example: flag a title claim that contradicts your real specialization"},
    {"severity": "note", "message": "link rendered as <a href> in body (https://example.com/portfolio) — use plain text"}
  ]
}
```

`clean` is false because real rules fired, not a guess — and every message
came from the YAML file, not from code that knows anything about a specific
person's career.

## Tools

| Tool | Status | Description |
|---|---|---|
| `search_jobs` | **working** | real search across Arbeitnow (free, no key), Adzuna and JSearch (API keys) — **verified live** against the Polish PHP market on both paid sources (10 real listings each, recognizable employers); results cached to protect JSearch's free quota |
| `fetch_job_posting` | **working** | single-URL extraction via `trafilatura` — **verified live, clean extraction** on JustJoin.it, NoFluffJobs, Bulldogjob, theprotocol.it, Solid.Jobs, CzyJestEldorado.pl, and LinkedIn single-posting pages; **confirmed, by design,** not to bypass Pracuj.pl/Indeed's Cloudflare bot-detection challenge |
| `render_pdf` | **working** | headless-Chrome HTML→PDF with the exact flags that avoid known hangs/silent failures; cross-platform `CHROME_PATH` auto-detection; page-count verification via raw PDF byte scan |
| `lint_cv` | **working** | configurable mechanical linter — banned phrases, skills-section-only bans, achievement-weight overclaims, title/GDPR/link checks, page-count limits, all driven by a YAML file you control |
| `log_application` | **working** | appends one row to a Markdown application registry in the correct section and date position, with a `column_map` for non-English headers; never invents free-text content |
| `list_applications` | **working** | read-only query over the registry (filter by portal/company) — use before `log_application` to check for a duplicate |
| `update_application_status` | **working** | rewrites one row's status cell in place; refuses to guess when more than one row matches |

## Verified job-board coverage (`fetch_job_posting`, 2026-10-19)

| Site | Result |
|---|---|
| JustJoin.it | ✅ clean extraction |
| NoFluffJobs | ✅ clean extraction |
| Bulldogjob | ✅ clean extraction |
| theprotocol.it | ✅ clean extraction |
| Solid.Jobs | ✅ clean extraction |
| CzyJestEldorado.pl (aggregator) | ✅ clean extraction |
| LinkedIn (`/jobs/view/<id>`) | ✅ clean extraction — the single-posting view is public |
| Jooble | N/A — redirects to the source site (e.g. JustJoin.it); nothing of its own to fetch |
| Pracuj.pl | ❌ blocked — active Cloudflare challenge, not attempted |
| Indeed (`pl.indeed.com`) | ❌ blocked — active Cloudflare challenge, not attempted |

## Why a configurable linter, not a hardcoded one

The original motivation: a CV draft once conflated two separate true facts
into one false-sounding claim, and it shipped before anyone caught it. A
grep-based mechanical check can catch a banned phrase; it can't catch
semantic conflation — that still needs a human or an independent adversarial
review. What a mechanical linter *can* do reliably: enforce *your own*
banned-phrase list, page limits, and required clauses, consistently, every
time, without you re-checking the same things by hand. `lint_cv` is that —
generic, so anyone can point it at their own facts.

## Development

```bash
.venv/bin/python -m pytest --cov     # tests + coverage
.venv/bin/ruff check .               # lint
.venv/bin/mypy src                   # types
.venv/bin/bandit -c pyproject.toml -r src   # security
.venv/bin/pip-audit                  # dependency vulnerabilities
```

Run `.venv/bin/pre-commit install` once to run all of the above (except
`pip-audit`, which needs network access and stays CI-only) on every commit.

One manual end-to-end check (not run in CI — needs live network and a real
Chrome install), also documented in `CHANGELOG.md`:

1. `search_jobs(keywords="PHP", remote_only=True, sources=["arbeitnow"])` against
   the live Arbeitnow API.
2. `fetch_job_posting(url=...)` on a URL from step 1.
3. `render_pdf(html_path=...)` on a sample CV, confirm `success` and `page_count`.
4. `lint_cv(html_path=...)` on a file with a seeded violation, confirm it's reported.
5. `log_application(..., dry_run=True)` against your own registry, confirm the
   previewed row and insertion point look right before dropping `dry_run`.

See `CHANGELOG.md` for what changed in each release.

## License

MIT — see [LICENSE](LICENSE).
