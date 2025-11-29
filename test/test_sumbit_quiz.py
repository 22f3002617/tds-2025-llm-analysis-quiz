import os

import pytest
from fastapi.testclient import TestClient
os.environ["SYSTEM_PROMPT_RESPONSE_ID"] = "resp_00fb93ee4f15a55600692ab023fb0081948d2e0507d11d8b56"

@pytest.mark.usefixtures("valid_secret")
def test_submit_quiz_invalid_secret(client: TestClient, quiz_payload):
    payload = quiz_payload(secret="invalid_secret")
    response = client.post("/submit-quiz", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid secret"


def test_submit_quiz_invalid_json(client: TestClient):
    response = client.post(
        "/submit-quiz",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON payload"


def test_submit_quiz_valid(client: TestClient, quiz_payload):
    payload = quiz_payload()
    response = client.post("/submit-quiz", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "success"}
