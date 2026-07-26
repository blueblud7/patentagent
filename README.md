# patent-copilot

`patent-copilot` is an MCP server for patent workflow assistance. The v0.1 focus is narrow:

- `search_prior_art(query, jurisdiction, date_before)`
- `build_claim_chart(claim_text, prior_art_ids)`

The main feature is an evidence-grounded claim chart: claim elements are decomposed, mapped to cited prior-art passages, and marked with confidence and gaps.

## Current Status

Implemented:

- Python package scaffold for an MCP server.
- `build_claim_chart` core pipeline with claim decomposition, evidence retrieval, mapping status, confidence, gaps, row-level review flags, chart-level review summaries, JSON output, and Markdown output.
- CSV output for claim-chart rows.
- Multi-reference per-element mapping details in JSON output.
- LLM-ready prompt boundaries for claim decomposition and evidence mapping.
- Patent ID normalization for common forms such as `US 12,345,678 B2` and Google Patents URLs.
- `search_prior_art` MCP tool wrapper with a PatentsView adapter boundary and keyless fallback guidance.
- `build_claim_chart` ID fetching via optional PatentsView first, including granted and pre-grant publication claims, detailed description, and summary text endpoints, then keyless Google Patents page fetch fallback.
- Partial ID-fetch fallback: PatentsView hits are kept and only missing IDs are retried through Google Patents.
- Manual prior-art text path for local demos and tests without API keys.
- Sample requests, Google Patents parser fixture, 6 golden fixtures, and validation script.
- Golden fixture quality scoring for claim-chart regressions.
- MCP smoke script that reports missing optional server dependencies instead of failing opaque imports.
- MCP integration smoke that starts the server over stdio, lists tools, calls both v0.1 tools, and verifies response schema plus review-summary consistency.
- Optional live PatentsView retrieval smoke for API-key environments.
- Prompt-only LLM mapping abstraction for future model-backed claim element mapping.

Not yet implemented:

- Production-grade patent text retrieval across USPTO/EPO/KIPRIS/Google Patents.
- Live LLM-assisted legal/technical mapping execution.
- Multi-reference charts and practitioner editing UX.
- Claim drafting/revision assistance that flags antecedent-basis issues, unsupported breadth, missing dependencies, inconsistent terminology, and amendment options.

## Production Readiness Direction

The next quality bar is real-world defensibility, not just happy-path demo output:

1. Retrieval should report source coverage for every reference, including which sections were fetched and which critical sections are missing.
2. Every mapping should remain evidence-backed and should preserve enough provenance for a practitioner to audit the quote.
3. Provider failures should be explicit and recoverable, because patent data sources change, rate-limit, and return partial records.
4. LLM-assisted mapping should be introduced behind the existing mapping boundary with deterministic fallbacks and JSON validation.
5. Evaluation should grow from golden demos to mixed real-world sets that include weak references, missing descriptions, dependent claims, and multi-reference combinations.

Current v0.1 output includes `document_coverage` and `warnings` so consumers can distinguish full-text support from title/abstract-only mappings.
The deterministic mapper also caps title/abstract-only evidence below `Disclosed` even when term overlap is strong; claims or description support is required before a limitation can be marked fully disclosed.
Evidence rows include `matched_terms`, `missing_terms`, `term_coverage`, and row-level `review_flags` so reviewers can see which material terms drove the score and filter limitations that still need legal/technical review. The top-level `review_summary` is also covered by evaluation so regressions that remove triage metadata are caught before release.

ID-based retrieval is implemented as a provider chain. The default chain tries PatentsView first and then Google Patents for any unresolved IDs. Each provider attempt is returned in `retrieval_attempts`, including requested IDs, found IDs, missing IDs, status, and error text when available. This keeps the tool usable if a free source changes access rules, pauses service, or returns partial records.

The release-readiness audit gives the current repo a repeatable score. A keyless local run can reach release-candidate status, but full `production_ready_v0.1` status requires the live PatentsView retrieval smoke to pass in the target environment.

## Legal Notice

This tool is for research and drafting assistance only. It is not legal advice. All outputs must be reviewed by a qualified patent professional before use.

## License

MIT. See `LICENSE`.

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Check runtime readiness:

```bash
PYTHONPATH=src python3 -m patent_copilot.preflight_cli
# After installation:
patent-copilot-preflight
```

The preflight output includes dependency/capability status plus a `live_validation` block showing the selected live patent ID and strict release-check command. The core offline demo and validation scripts can run without installed MCP dependencies. The packaged MCP server runtime requires Python 3.11+ and the `mcp` package.

## Run MCP Server

```bash
patent-copilot
```

For local development without external patent APIs, pass manual prior-art text directly to `build_claim_chart`:

```json
{
  "claim_text": "1. A system comprising: a processor configured to receive sensor data; and a memory storing instructions to classify the sensor data.",
  "prior_art_texts": [
    {
      "id": "US-DEMO-1",
      "title": "Sensor classification system",
      "abstract": "A processor receives sensor measurements and classifies the measurements using stored instructions.",
      "claims": "",
      "description": "[0042] The processor receives sensor data from an input interface. [0043] Memory stores instructions that classify the sensor data."
    }
  ]
}
```

You can also pass patent IDs:

```json
{
  "claim_text": "1. A system comprising: a processor configured to receive sensor data; and a memory storing instructions to classify the sensor data.",
  "prior_art_ids": ["US12345678B2"]
}
```

For ID-based fetching, v0.1 tries PatentsView when `PATENTSVIEW_API_KEY` is configured. It first fetches patent/publication metadata, then enriches granted patents from `g_claim`, `g_detail_desc_text`, and `g_brf_sum_text` endpoints, and pre-grant publications from `pg_claim`, `pg_detail_desc_text`, and `pg_brf_sum_text` endpoints when available. It keeps any documents it finds, then falls back to fetching only missing IDs from matching Google Patents pages. The fallback is useful for demos and targeted references, not bulk searching.

## MCP Response Contracts

MCP tool responses use an explicit `ok` flag. Clients should check this before reading result fields.

`search_prior_art` success:

```json
{
  "ok": true,
  "schema_version": "1.0",
  "provider": "patentsview",
  "results": [],
  "warnings": []
}
```

If PatentsView search is unavailable, v0.1 returns `ok: true` with `provider: "google_patents"` and a fallback guidance result instead of failing the call.

`build_claim_chart` success includes:

```json
{
  "ok": true,
  "schema_version": "1.0",
  "claim_text": "...",
  "rows": [],
  "review_summary": {},
  "markdown": "...",
  "csv": "...",
  "document_coverage": [],
  "retrieval_attempts": [],
  "warnings": []
}
```

`claim_text` must be non-empty. Provide either `prior_art_texts` or non-empty `prior_art_ids`; empty patent ID values are rejected as `invalid_request`.
`build_claim_chart` accepts at most 25 total prior-art references per request. Each manual `prior_art_texts` item must include a non-empty `id` and at least one text field among `title`, `abstract`, `claims`, or `description`.

Each evidence item may include `matched_terms`, `missing_terms`, and `term_coverage`. Each claim-chart row may include `review_flags` such as `no_evidence`, `weak_section_support`, `low_term_coverage`, `missing_terms`, and `needs_practitioner_review`. The top-level `review_summary` aggregates mapping counts, confidence counts, review flag counts, rows requiring review, and highest-risk flags for quick triage. CSV output also includes best-evidence section, locator, quote, matched terms, missing terms, term coverage, and review flag columns for spreadsheet review. Each document coverage item reports source, sections, character count, URL, and warnings. Chart-level warnings also flag normalized duplicate patent IDs so reviewers can catch repeated references before relying on the chart. If PatentsView metadata succeeds but optional text endpoints fail, those endpoint failures are preserved in document metadata and surfaced as coverage warnings.

Recoverable failures return:

```json
{
  "ok": false,
  "schema_version": "1.0",
  "error": {
    "code": "invalid_request",
    "message": "...",
    "recoverable": true,
    "next_steps": []
  }
}
```

Retrieval failures also include `retrieval_attempts` so the client can show which providers were tried.
Unexpected server-side failures return `ok: false` with `error.code: "internal_error"` and `recoverable: false`, so clients can show a stable failure shape without treating it as bad user input.

## Run Offline Demo

This path does not require API keys or external patent services:

```bash
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format json
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format summary
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format csv
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format csv --output dist/demo_chart.csv
# After installation:
patent-copilot-demo examples/build_claim_chart_request.json
```

Expected result: a three-row claim chart with evidence for the processor and memory elements. The `summary` format emits only `claim_text`, `review_summary`, `warnings`, and `document_coverage` for fast triage.
The offline demo uses the same 25-reference cap as the MCP `build_claim_chart` tool.
The offline demo does not fetch `prior_art_ids`; provide `prior_art_texts` for that path, or use the MCP `build_claim_chart` tool with network retrieval configured.

## MCP Configuration Example

```json
{
  "mcpServers": {
    "patent-copilot": {
      "command": "patent-copilot"
    }
  }
}
```

## Environment Variables

- `PATENTSVIEW_API_KEY`: optional. Used for PatentsView search/fetch. Without it, `search_prior_art` returns fallback guidance and `build_claim_chart` can still fetch specific patent IDs through Google Patents pages when network/dependencies are available.
- `PATENT_COPILOT_LIVE_PATENT_ID`: optional. Overrides the patent ID used by live retrieval smoke checks.

Use `.env.example` as the local template. Do not commit real API keys.

## PatentsView Access Notes

PatentsView data is public/open-access, but the current PatentSearch API requires an API key in the `X-Api-Key` header. PatentsView documentation lists a 45 requests/minute limit per API key and notes that key availability and API behavior may change. USPTO also announced a 2026 migration of PatentsView functions to the Open Data Portal, so final production validation should always run in the target environment with the real key:

```bash
PATENTSVIEW_API_KEY=... patent-copilot-release-check --require-live
PATENTSVIEW_API_KEY=... patent-copilot-release-check --require-live --patent-id US20240000001A1
```

Operationally, treat PatentsView as a free/public data source with access controls and service limits, not as an unauthenticated always-on dependency.

References:

- https://search.patentsview.org/docs/docs/Search%20API/SearchAPIReference/
- https://www.uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20

## v0.1 Design

`build_claim_chart` works in four stages:

1. Decompose the claim into numbered elements.
2. Retrieve candidate evidence passages from each prior-art document.
3. Map each claim element to the strongest evidence.
4. Emit structured JSON, a Markdown chart, and CSV rows.

The implementation intentionally refuses to mark an element as disclosed unless it has supporting text. Missing or weak evidence is reported as a gap, as structured row-level review flags, and in the chart-level review summary.

`search_prior_art` is intentionally conservative in v0.1. PatentsView powers API search when a key is available. Without a key, the tool returns a structured result explaining that specific `prior_art_ids` should be supplied.

## Development

```bash
pytest
ruff check .
```

If dev dependencies are not installed, run the repository-local validation script:

```bash
PYTHONPATH=src python3 scripts/validate.py
```

Run the local CI-equivalent checks:

```bash
python scripts/ci_check.py
```

Run golden fixture scoring:

```bash
PYTHONPATH=src python3 scripts/evaluate_golden.py
PYTHONPATH=src python3 scripts/evaluate_golden.py --json
# After installation:
patent-copilot-eval
```

Golden fixture scoring checks row count, evidence coverage, reference mapping coverage, expected supported terms, expected gaps, unsupported `Disclosed` rows, weak-section disclosures, weak-term disclosures, review summary completeness, gap coverage, and source quality.

Run MCP smoke:

```bash
PYTHONPATH=src python3 scripts/smoke_mcp.py
# After installation:
patent-copilot-smoke
```

If `mcp` is not installed, the smoke script reports that clearly while still checking the tool-layer imports.

Run the live stdio MCP integration smoke:

```bash
PYTHONPATH=src python3 scripts/smoke_mcp_integration.py
# After installation:
patent-copilot-mcp-integration
```

Run the optional live PatentsView retrieval smoke when a key is available:

```bash
PATENTSVIEW_API_KEY=... patent-copilot-live-retrieval-smoke
# Optional override:
PATENT_COPILOT_LIVE_PATENT_ID=US12000000B2 patent-copilot-live-retrieval-smoke
patent-copilot-live-retrieval-smoke --patent-id US20240000001A1
patent-copilot-live-retrieval-smoke --output dist/live_retrieval_smoke.json
# Strict final-readiness proof:
PATENTSVIEW_API_KEY=... patent-copilot-live-retrieval-smoke --require-api-key
```

Without `PATENTSVIEW_API_KEY`, this command exits successfully with a skipped status unless `--require-api-key` is set. The strict flag is intended for final environment validation. Prefer recent grant or publication IDs for this check; PatentsView long-text endpoint coverage is currently concentrated in recent years.

Build release artifacts:

```bash
python -m build
python scripts/check_distribution.py --output dist/distribution_check.json
python scripts/smoke_installed_wheel.py
```

Run the full local release gate:

```bash
python scripts/release_check.py
# After installation:
patent-copilot-release-check
```

The release gate runs unit tests, lint, local CI checks, builds sdist/wheel artifacts, verifies distribution contents and wheel metadata, installs the built wheel into a temporary environment for an offline smoke test including JSON, summary, and file output, runs the optional live retrieval smoke, prints a readiness score, and writes `dist/distribution_check.json`, `dist/installed_wheel_smoke.json`, `dist/readiness_report.json`, `dist/live_retrieval_smoke.json`, and `dist/release_manifest.json`.
The distribution report includes wheel/sdist size and SHA-256 fields for artifact traceability.
The release manifest records the executed release-gate steps, command arguments, return codes, elapsed seconds, report paths, strict-live setting, selected patent ID, and whether a PatentsView API key was configured. It does not record the API key value.
The readiness report includes `schema_version`, `package_version`, `generated_at`, `evidence`, `evidence_artifacts`, `evidence_artifact_status`, `evidence_artifact_errors`, `evidence_flag_errors`, `summary`, and `next_commands` fields so CI or release automation can parse the current decision, locate supporting JSON artifacts, confirm whether they exist, verify that they are valid JSON with expected top-level keys, identify artifact or flag mismatch failures, and find the next required validation step safely. Missing, invalid, structurally incomplete, internally failed, or flag-inconsistent evidence artifacts are release blockers even when the corresponding command-line flags are passed.
The build step may need network access to install isolated PEP 517 build dependencies.
For final production-readiness proof in an API-key environment, require live PatentsView retrieval:

```bash
PATENTSVIEW_API_KEY=... patent-copilot-release-check --require-live
```

Run only the readiness audit:

```bash
python scripts/readiness_audit.py --release-gate-passed --distribution-check-passed --installed-wheel-smoke-passed --output dist/readiness_report.json
# After installation:
patent-copilot-readiness-audit --release-gate-passed --distribution-check-passed --installed-wheel-smoke-passed --output dist/readiness_report.json
```

## CI

GitHub Actions runs on Python 3.11 and installs the package with dev dependencies. The workflow runs:

- `pytest`
- `ruff check .`
- `python scripts/validate.py`
- `patent-copilot-eval --json`
- `patent-copilot-preflight`
- `patent-copilot-smoke`
- `patent-copilot-mcp-integration`
- `python -m build`
- `python scripts/check_distribution.py --output dist/distribution_check.json`
- `patent-copilot-installed-wheel-smoke --output dist/installed_wheel_smoke.json`
- `patent-copilot-live-retrieval-smoke --output dist/live_retrieval_smoke.json`
- `patent-copilot-live-retrieval-smoke --require-api-key --output dist/live_retrieval_smoke.json` when `PATENTSVIEW_API_KEY` is configured as a CI secret.
- `python scripts/write_release_manifest.py`
- `python scripts/write_release_manifest.py --require-live` when the strict live smoke passes.
- `python scripts/readiness_audit.py --release-gate-passed --distribution-check-passed --installed-wheel-smoke-passed --output dist/readiness_report.json`
- `python scripts/readiness_audit.py --release-gate-passed --distribution-check-passed --installed-wheel-smoke-passed --live-retrieval-passed --output dist/readiness_report.json` when the strict live smoke passes.
- Uploads wheel, sdist, `dist/distribution_check.json`, `dist/installed_wheel_smoke.json`, `dist/readiness_report.json`, `dist/live_retrieval_smoke.json`, and `dist/release_manifest.json` as CI artifacts.

## Next Phase

After v0.1 release validation, the next product phase should add a claim drafting and revision assistant. The expected scope is to review claim sets for antecedent basis, dependency structure, inconsistent terms, unsupported breadth, missing fallback positions, and amendment candidates while preserving the existing evidence-grounded charting workflow.

## LLM Mapping Boundary

`src/patent_copilot/core/mapping.py` defines the model integration boundary. The current `PromptOnlyMappingModel` builds the practitioner-oriented evidence-mapping prompt without calling an external model. A future model adapter should implement the same `map_element(element, document, evidence)` shape and return a parsed `ReferenceMapping`.
