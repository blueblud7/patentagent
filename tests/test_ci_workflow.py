from pathlib import Path


def test_ci_uses_patentsview_secret_for_conditional_live_readiness() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "PATENTSVIEW_API_KEY: ${{ secrets.PATENTSVIEW_API_KEY }}" in workflow
    assert "python scripts/check_distribution.py --output dist/distribution_check.json" in workflow
    assert (
        "patent-copilot-installed-wheel-smoke --output dist/installed_wheel_smoke.json"
        in workflow
    )
    assert (
        "patent-copilot-live-retrieval-smoke --require-api-key "
        "--output dist/live_retrieval_smoke.json"
    ) in workflow
    assert "python scripts/write_release_manifest.py --require-live" in workflow
    assert "if: ${{ env.PATENTSVIEW_API_KEY != '' }}" in workflow
    assert "--live-retrieval-passed --output dist/readiness_report.json" in workflow
    assert "dist/live_retrieval_smoke.json" in workflow
    assert "dist/release_manifest.json" in workflow


def test_ci_keeps_keyless_readiness_path() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "if: ${{ env.PATENTSVIEW_API_KEY == '' }}" in workflow
    assert "dist/distribution_check.json" in workflow
    assert "dist/installed_wheel_smoke.json" in workflow
    assert (
        "python scripts/readiness_audit.py --release-gate-passed "
        "--distribution-check-passed --installed-wheel-smoke-passed "
        "--output dist/readiness_report.json"
    ) in workflow
    assert "patent-copilot-live-retrieval-smoke --output dist/live_retrieval_smoke.json" in workflow
    assert "python scripts/write_release_manifest.py" in workflow
