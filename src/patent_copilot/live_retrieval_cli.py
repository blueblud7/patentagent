from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from patent_copilot.adapters.patentsview import PatentsViewAdapter
from patent_copilot.config import clean_env_value, env_has_value, get_env_value

DEFAULT_LIVE_PATENT_ID = "US12000000B2"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a live PatentsView retrieval smoke check.")
    parser.add_argument(
        "--require-api-key",
        action="store_true",
        help="Fail instead of skipping when PATENTSVIEW_API_KEY is not configured.",
    )
    parser.add_argument(
        "--patent-id",
        help=(
            "Patent or publication ID to fetch. Defaults to PATENT_COPILOT_LIVE_PATENT_ID "
            "or US12000000B2."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the live retrieval smoke JSON result.",
    )
    args = parser.parse_args(argv)
    patent_id = clean_env_value(args.patent_id)
    if args.patent_id is not None and patent_id is None:
        parser.error("--patent-id must not be blank")
    return asyncio.run(
        _main(
            require_api_key=args.require_api_key,
            patent_id=patent_id,
            output_path=args.output,
        )
    )


async def _main(
    *,
    require_api_key: bool = False,
    patent_id: str | None = None,
    output_path: Path | None = None,
) -> int:
    start = perf_counter()
    api_key_configured = env_has_value("PATENTSVIEW_API_KEY")
    status: dict[str, Any] = {
        "skipped": False,
        "require_api_key": require_api_key,
        "api_key_configured": api_key_configured,
        "patent_id": patent_id or get_env_value("PATENT_COPILOT_LIVE_PATENT_ID") or DEFAULT_LIVE_PATENT_ID,
        "provider": "patentsview",
        "fetched_document_id": None,
        "document_url": None,
        "record_type": None,
        "documents_fetched": 0,
        "text_sources": [],
        "optional_endpoint_errors": [],
        "has_claims": False,
        "has_description": False,
        "elapsed_seconds": 0.0,
        "note": (
            "Default ID is a 2024 grant because PatentsView long-text endpoint "
            "coverage is currently concentrated in recent grant years."
        ),
        "message": "",
    }

    if not api_key_configured:
        status["skipped"] = True
        status["message"] = "PATENTSVIEW_API_KEY is not configured; live retrieval smoke skipped."
        return _finish(status, start, 1 if require_api_key else 0, output_path=output_path)

    try:
        documents = await PatentsViewAdapter().fetch_documents([status["patent_id"]])
    except (RuntimeError, ValueError, httpx.HTTPError) as exc:
        status["message"] = f"live PatentsView retrieval failed: {exc}"
        return _finish(status, start, 1, output_path=output_path)

    status["documents_fetched"] = len(documents)
    if not documents:
        status["message"] = "PatentsView returned no document for the requested live patent ID."
        return _finish(status, start, 1, output_path=output_path)

    document = documents[0]
    text_sources = document.metadata.get("text_sources", [])
    optional_endpoint_errors = document.metadata.get("optional_endpoint_errors", [])
    status["text_sources"] = text_sources if isinstance(text_sources, list) else []
    status["optional_endpoint_errors"] = (
        optional_endpoint_errors if isinstance(optional_endpoint_errors, list) else []
    )
    status["fetched_document_id"] = document.id
    status["document_url"] = document.url
    status["record_type"] = document.metadata.get("record_type", "grant")
    status["has_claims"] = bool(document.claims)
    status["has_description"] = bool(document.description)

    if not status["has_claims"]:
        status["message"] = "PatentsView live retrieval did not return claims text."
        return _finish(status, start, 1, output_path=output_path)
    if not status["has_description"]:
        status["message"] = "PatentsView live retrieval did not return description or summary text."
        return _finish(status, start, 1, output_path=output_path)

    status["message"] = "live PatentsView retrieval smoke passed"
    return _finish(status, start, 0, output_path=output_path)


def _finish(
    status: dict[str, Any],
    start: float,
    return_code: int,
    *,
    output_path: Path | None = None,
) -> int:
    status["elapsed_seconds"] = round(perf_counter() - start, 3)
    status_json = json.dumps(status, indent=2)
    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(f"{status_json}\n", encoding="utf-8")
        except OSError as exc:
            print(f"could not write live retrieval smoke output: {exc}", file=sys.stderr)
            return 1
    print(status_json)
    return return_code

if __name__ == "__main__":
    raise SystemExit(main())
