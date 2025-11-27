import sys
from pathlib import Path
import importlib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
for path in (PROJECT_ROOT, APP_DIR):
    if str(path) not in sys.path:
        sys.path.append(str(path))

config = importlib.import_module("config")
sys.modules.setdefault("app.config", config)

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def test_app():
    return fastapi_app


@pytest.fixture()
def client(test_app):
    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture()
def valid_secret(monkeypatch):
    secret = "test-secret"
    monkeypatch.setattr(config, "SECRET_KEY", secret)
    return secret


@pytest.fixture()
def quiz_payload(valid_secret):
    def _payload(**overrides):
        payload = {
            "email": "dummy@example.com",
            "secret": valid_secret,
            "url": "https://tds-llm-analysis.s-anand.net/demo",
        }
        payload.update(overrides)
        return payload

    return _payload
