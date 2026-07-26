from patent_copilot.config import clean_env_value, env_has_value, get_env_value


def test_clean_env_value_treats_none_and_blank_as_missing() -> None:
    assert clean_env_value(None) is None
    assert clean_env_value("") is None
    assert clean_env_value("   ") is None


def test_clean_env_value_strips_configured_value() -> None:
    assert clean_env_value("  test-key  ") == "test-key"


def test_get_env_value_and_env_has_value_share_blank_semantics(monkeypatch) -> None:
    monkeypatch.setenv("PATENT_COPILOT_TEST_ENV", "   ")
    assert get_env_value("PATENT_COPILOT_TEST_ENV") is None
    assert not env_has_value("PATENT_COPILOT_TEST_ENV")

    monkeypatch.setenv("PATENT_COPILOT_TEST_ENV", " live ")
    assert get_env_value("PATENT_COPILOT_TEST_ENV") == "live"
    assert env_has_value("PATENT_COPILOT_TEST_ENV")
