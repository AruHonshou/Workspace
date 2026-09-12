from job_orchestrator.config import Settings


def test_deepseek_configuration_uses_the_official_endpoint(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-v4-pro"
    assert settings.deepseek_max_concurrency == 1
