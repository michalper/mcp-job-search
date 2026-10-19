# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/) (pre-1.0:
a minor bump means new features, a patch means fixes only — no stability
guarantee yet on the exact JSON shape of tool results).

## [0.1.1] - 2026-10-19

### Changed
- Improved `lint_cv`'s tool and `pdf_path` parameter descriptions per
  Glama's Tool Definition Quality Score feedback: states explicit
  read-only/no-mutation behavior, explains what `pdf_path` actually changes
  rather than restating the schema, and gives explicit usage guidance
  relative to `render_pdf`.
- README documents the published PyPI/registry locations and `pip`/`uvx`
  install instructions.

## [0.1.0] - 2026-10-19

### Added
- Five tools: `search_jobs` (Arbeitnow/Adzuna/JSearch), `fetch_job_posting`
  (single-URL extraction via `trafilatura`), `render_pdf` (headless Chrome),
  `lint_cv` (configurable rules engine, YAML-driven), `log_application`
  (Markdown registry logging with a `column_map` for non-English headers).
- `search_jobs` result caching (`SEARCH_CACHE_DIR`/`SEARCH_CACHE_TTL_SECONDS`)
  to protect JSearch's 200-requests/month free quota.
- `CHROME_PATH` auto-detection across macOS/Linux/Windows for `render_pdf`
  (was hardcoded to a macOS app bundle path in earlier drafts).

### Fixed
- JSearch integration caught three bugs only visible from a real request: the
  correct endpoint is `/search-v2` not `/search` (404 otherwise), results
  nest under `data.jobs` not a flat `data` list, and `country` must be set
  explicitly via `JSEARCH_COUNTRY` — it does not infer from free-text
  `location` and defaults server-side to `us`.

### Verified live
- `fetch_job_posting`: clean extraction from JustJoin.it, NoFluffJobs,
  Bulldogjob, theprotocol.it, Solid.Jobs, CzyJestEldorado.pl, and LinkedIn
  single-posting pages. Confirmed **by design** failures on Pracuj.pl and
  Indeed — both sit behind an active Cloudflare bot-detection challenge
  (`cf-mitigated: challenge` / 401 with a Cloudflare bot-management cookie),
  which this tool will not attempt to solve automatically.
- `search_jobs`: Adzuna (`adzuna.pl`) and JSearch (with `JSEARCH_COUNTRY=pl`)
  both returned real, current Polish PHP listings from recognizable
  employers.
- `render_pdf` and `log_application` exercised against a real CV fixture and
  the maintainer's own application registry (with a dry-run/revert cycle).
