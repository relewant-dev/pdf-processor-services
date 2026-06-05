from __future__ import annotations

import os
from pathlib import Path

import config


def test_load_dotenv_adds_missing_values_without_overriding_existing(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local overrides",
                "OLLAMA_MODEL=qwen3-vl:4b",
                "export OLLAMA_URL=http://localhost:11434",
                "LOG_LEVEL=DEBUG",
                'LOG_FILE="quoted.log"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.delenv("LOG_FILE", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)

    config._load_dotenv(env_file)

    assert os.environ["OLLAMA_MODEL"] == "qwen3-vl:4b"
    assert os.environ["OLLAMA_URL"] == "http://localhost:11434"
    assert os.environ["LOG_LEVEL"] == "WARNING"
    assert os.environ["LOG_FILE"] == "quoted.log"
