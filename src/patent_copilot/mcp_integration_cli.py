from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from patent_copilot.contracts import MCP_RESPONSE_SCHEMA_VERSION

CLAIM_TEXT = (
    "1. A system comprising: a processor configured to receive sensor data; "
    "and a memory storing instructions to classify the sensor data."
)
PRIOR_ART_TEXTS = [
    {
        "id": "US-DEMO-1",
        "title": "Sensor classification system",
        "abstract": (
            "A processor receives sensor measurements and classifies the measurements "
            "using stored instructions."
        ),
        "claims": "A system including a processor and memory for processing sensor measurements.",
        "description": (
            "[0042] The processor receives sensor data from an input interface. "
            "[0043] Memory stores instructions that classify the sensor data."
        ),
    }
]


def main() -> int:
    return asyncio.run(asyncio.wait_for(_main(), timeout=15))


async def _main() -> int:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "patent_copilot.server"],
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    status: dict[str, Any] = {
        "server_started": False,
        "tools_listed": False,
        "search_prior_art_called": False,
        "build_claim_chart_called": False,
        "input_schema_checked": False,
        "schema_version_checked": False,
        "review_summary_checked": False,
        "message": "",
    }

    try:
        async with stdio_client(server_params) as streams:
            status["server_started"] = True
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                expected_tools = {"search_prior_art", "build_claim_chart"}
                missing_tools = expected_tools - tool_names
                if missing_tools:
                    status["message"] = f"missing MCP tools: {sorted(missing_tools)}"
                    print(json.dumps(status, indent=2))
                    return 1
                schema_error = _input_schema_error({tool.name: tool.inputSchema for tool in tools.tools})
                if schema_error:
                    status["message"] = schema_error
                    print(json.dumps(status, indent=2))
                    return 1
                status["input_schema_checked"] = True
                status["tools_listed"] = True

                search_result = await session.call_tool(
                    "search_prior_art",
                    {
                        "query": "sensor classification processor memory",
                        "jurisdiction": "US",
                        "limit": 1,
                    },
                )
                if search_result.isError:
                    status["message"] = "search_prior_art returned an MCP error"
                    print(json.dumps(status, indent=2))
                    return 1
                search_payload = _tool_payload(search_result)
                if search_payload.get("ok") is not True:
                    status["message"] = "search_prior_art did not return ok=true"
                    print(json.dumps(status, indent=2))
                    return 1
                if "results" not in search_payload:
                    status["message"] = "search_prior_art response did not include results"
                    print(json.dumps(status, indent=2))
                    return 1
                if search_payload.get("schema_version") != MCP_RESPONSE_SCHEMA_VERSION:
                    status["message"] = "search_prior_art response schema_version mismatch"
                    print(json.dumps(status, indent=2))
                    return 1
                status["search_prior_art_called"] = True

                chart_result = await session.call_tool(
                    "build_claim_chart",
                    {
                        "claim_text": CLAIM_TEXT,
                        "prior_art_texts": PRIOR_ART_TEXTS,
                    },
                )
                if chart_result.isError:
                    status["message"] = "build_claim_chart returned an MCP error"
                    print(json.dumps(status, indent=2))
                    return 1
                chart_payload = _tool_payload(chart_result)
                if chart_payload.get("ok") is not True:
                    status["message"] = "build_claim_chart did not return ok=true"
                    print(json.dumps(status, indent=2))
                    return 1
                rows = chart_payload.get("rows", [])
                if len(rows) != 3:
                    status["message"] = f"expected 3 claim-chart rows, got {len(rows)}"
                    print(json.dumps(status, indent=2))
                    return 1
                if not any(row.get("mapping") == "Disclosed" for row in rows):
                    status["message"] = "claim chart did not include any disclosed mappings"
                    print(json.dumps(status, indent=2))
                    return 1
                review_summary_error = _review_summary_error(chart_payload)
                if review_summary_error:
                    status["message"] = review_summary_error
                    print(json.dumps(status, indent=2))
                    return 1
                if chart_payload.get("schema_version") != MCP_RESPONSE_SCHEMA_VERSION:
                    status["message"] = "build_claim_chart response schema_version mismatch"
                    print(json.dumps(status, indent=2))
                    return 1
                status["build_claim_chart_called"] = True
                status["schema_version_checked"] = True
                status["review_summary_checked"] = True
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        status["message"] = f"MCP integration smoke failed: {exc}"
        print(json.dumps(status, indent=2))
        return 1

    status["message"] = "MCP integration smoke passed"
    print(json.dumps(status, indent=2))
    return 0


def _tool_payload(result: Any) -> dict[str, Any]:
    if result.structuredContent is not None:
        return result.structuredContent
    for item in result.content:
        if getattr(item, "type", None) == "text":
            payload = json.loads(item.text)
            if isinstance(payload, dict):
                return payload
    raise ValueError("tool result did not include a JSON object payload")


def _input_schema_error(schemas: dict[str, dict[str, Any]]) -> str | None:
    search_schema = schemas.get("search_prior_art", {})
    search_properties = search_schema.get("properties", {})
    jurisdiction = search_properties.get("jurisdiction", {})
    limit = search_properties.get("limit", {})
    date_before = search_properties.get("date_before", {})
    if jurisdiction.get("const") != "US":
        return "search_prior_art jurisdiction schema must be restricted to US"
    if limit.get("minimum") != 1 or limit.get("maximum") != 100:
        return "search_prior_art limit schema must be constrained to 1..100"
    if not _schema_has_pattern(date_before, r"^\d{4}-\d{2}-\d{2}$"):
        return "search_prior_art date_before schema must require YYYY-MM-DD"

    chart_schema = schemas.get("build_claim_chart", {})
    chart_properties = chart_schema.get("properties", {})
    claim_text = chart_properties.get("claim_text", {})
    prior_art_ids = chart_properties.get("prior_art_ids", {})
    prior_art_texts = chart_properties.get("prior_art_texts", {})
    if claim_text.get("minLength") != 1:
        return "build_claim_chart claim_text schema must be non-empty"
    if not _schema_has_max_items(prior_art_ids, 25):
        return "build_claim_chart prior_art_ids schema must cap references at 25"
    if not _schema_has_max_items(prior_art_texts, 25):
        return "build_claim_chart prior_art_texts schema must cap references at 25"
    return None


def _schema_has_pattern(schema: dict[str, Any], pattern: str) -> bool:
    if schema.get("pattern") == pattern:
        return True
    return any(
        isinstance(item, dict) and _schema_has_pattern(item, pattern)
        for item in schema.get("anyOf", [])
    )


def _schema_has_max_items(schema: dict[str, Any], max_items: int) -> bool:
    if schema.get("maxItems") == max_items:
        return True
    return any(
        isinstance(item, dict) and _schema_has_max_items(item, max_items)
        for item in schema.get("anyOf", [])
    )


def _review_summary_error(payload: dict[str, Any]) -> str | None:
    rows = payload.get("rows", [])
    summary = payload.get("review_summary")
    if not isinstance(rows, list):
        return "build_claim_chart rows must be a list"
    if not isinstance(summary, dict):
        return "build_claim_chart response must include review_summary"
    expected_mapping_counts = _count_values(str(row.get("mapping")) for row in rows)
    expected_confidence_counts = _count_values(str(row.get("confidence")) for row in rows)
    expected_review_flag_counts = _count_values(flag for row in rows for flag in _row_review_flags(row))
    expected_highest_risk_flags = [
        flag
        for flag in (
            "no_evidence",
            "weak_section_support",
            "low_term_coverage",
            "missing_terms",
            "needs_practitioner_review",
        )
        if expected_review_flag_counts.get(flag, 0) > 0
    ]
    rows_requiring_review = len([row for row in rows if row.get("review_flags")])
    if summary.get("total_rows") != len(rows):
        return "review_summary total_rows does not match rows"
    if summary.get("rows_requiring_review") != rows_requiring_review:
        return "review_summary rows_requiring_review does not match rows"
    if summary.get("needs_practitioner_review") != (rows_requiring_review > 0):
        return "review_summary needs_practitioner_review does not match rows"
    if summary.get("mapping_counts") != expected_mapping_counts:
        return "review_summary mapping_counts does not match rows"
    if summary.get("confidence_counts") != expected_confidence_counts:
        return "review_summary confidence_counts does not match rows"
    if summary.get("review_flag_counts") != expected_review_flag_counts:
        return "review_summary review_flag_counts does not match rows"
    if summary.get("highest_risk_flags") != expected_highest_risk_flags:
        return "review_summary highest_risk_flags does not match rows"
    return None


def _count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _row_review_flags(row: Any) -> list[str]:
    if not isinstance(row, dict):
        return []
    flags = row.get("review_flags", [])
    if not isinstance(flags, list):
        return []
    return [str(flag) for flag in flags]


if __name__ == "__main__":
    raise SystemExit(main())
