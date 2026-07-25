# patent-copilot

`patent-copilot` is an MCP server for patent workflow assistance. The v0.1 focus is narrow:

- `search_prior_art(query, jurisdiction, date_before)`
- `build_claim_chart(claim_text, prior_art_ids)`

The main feature is an evidence-grounded claim chart: claim elements are decomposed, mapped to cited prior-art passages, and marked with confidence and gaps.

## Legal Notice

This tool is for research and drafting assistance only. It is not legal advice. All outputs must be reviewed by a qualified patent professional before use.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

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

- `PATENTSVIEW_API_KEY`: optional. Required only when using the PatentsView adapter.

## v0.1 Design

`build_claim_chart` works in four stages:

1. Decompose the claim into numbered elements.
2. Retrieve candidate evidence passages from each prior-art document.
3. Map each claim element to the strongest evidence.
4. Emit both structured JSON and a Markdown chart.

The implementation intentionally refuses to mark an element as disclosed unless it has supporting text. Missing or weak evidence is reported as a gap.

## Development

```bash
pytest
ruff check .
```

