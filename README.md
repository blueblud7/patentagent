# patent-copilot

`patent-copilot` is an MCP server for patent workflow assistance. The v0.1 focus is narrow:

- `search_prior_art(query, jurisdiction, date_before)`
- `build_claim_chart(claim_text, prior_art_ids)`

The main feature is an evidence-grounded claim chart: claim elements are decomposed, mapped to cited prior-art passages, and marked with confidence and gaps.

## Current Status

Implemented:

- Python package scaffold for an MCP server.
- `build_claim_chart` core pipeline with claim decomposition, evidence retrieval, mapping status, confidence, gaps, JSON output, and Markdown output.
- CSV output for claim-chart rows.
- Multi-reference per-element mapping details in JSON output.
- LLM-ready prompt boundaries for claim decomposition and evidence mapping.
- Patent ID normalization for common forms such as `US 12,345,678 B2` and Google Patents URLs.
- `search_prior_art` MCP tool wrapper with a PatentsView adapter boundary and keyless fallback guidance.
- `build_claim_chart` ID fetching via optional PatentsView first, then keyless Google Patents page fetch fallback.
- Manual prior-art text path for local demos and tests without API keys.
- Sample requests, Google Patents parser fixture, 5 golden fixtures, and validation script.
- Golden fixture quality scoring for claim-chart regressions.
- MCP smoke script that reports missing optional server dependencies instead of failing opaque imports.
- Prompt-only LLM mapping abstraction for future model-backed claim element mapping.

Not yet implemented:

- Production-grade patent text retrieval across USPTO/EPO/KIPRIS/Google Patents.
- Live LLM-assisted legal/technical mapping execution.
- Multi-reference charts and practitioner editing UX.
- Full MCP integration test against a live client.

## Legal Notice

This tool is for research and drafting assistance only. It is not legal advice. All outputs must be reviewed by a qualified patent professional before use.

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

The core offline demo and validation scripts can run without installed MCP dependencies. The packaged MCP server runtime requires Python 3.11+ and the `mcp` package.

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

For ID-based fetching, v0.1 tries PatentsView when `PATENTSVIEW_API_KEY` is configured, then falls back to fetching the matching Google Patents page. The fallback is useful for demos and targeted references, not bulk searching.

## Run Offline Demo

This path does not require API keys or external patent services:

```bash
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format json
PYTHONPATH=src python3 -m patent_copilot.cli examples/build_claim_chart_request.json --format csv
```

Expected result: a three-row claim chart with evidence for the processor and memory elements.

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

## v0.1 Design

`build_claim_chart` works in four stages:

1. Decompose the claim into numbered elements.
2. Retrieve candidate evidence passages from each prior-art document.
3. Map each claim element to the strongest evidence.
4. Emit structured JSON, a Markdown chart, and CSV rows.

The implementation intentionally refuses to mark an element as disclosed unless it has supporting text. Missing or weak evidence is reported as a gap.

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

Run the local CI-equivalent checks that do not require installed entry points:

```bash
PYTHONPATH=src python3 scripts/ci_check.py
```

Run golden fixture scoring:

```bash
PYTHONPATH=src python3 scripts/evaluate_golden.py
PYTHONPATH=src python3 scripts/evaluate_golden.py --json
# After installation:
patent-copilot-eval
```

Run MCP smoke:

```bash
PYTHONPATH=src python3 scripts/smoke_mcp.py
# After installation:
patent-copilot-smoke
```

If `mcp` is not installed, the smoke script reports that clearly while still checking the tool-layer imports.

## CI

GitHub Actions runs on Python 3.11 and installs the package with dev dependencies. The workflow runs:

- `pytest`
- `python scripts/validate.py`
- `patent-copilot-eval --json`
- `patent-copilot-preflight`
- `patent-copilot-smoke`

## LLM Mapping Boundary

`src/patent_copilot/core/mapping.py` defines the model integration boundary. The current `PromptOnlyMappingModel` builds the practitioner-oriented evidence-mapping prompt without calling an external model. A future model adapter should implement the same `map_element(element, document, evidence)` shape and return a parsed `ReferenceMapping`.
