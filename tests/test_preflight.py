from patent_copilot.preflight_cli import MIN_RUNTIME


def test_preflight_runtime_floor() -> None:
    assert MIN_RUNTIME == (3, 11)

