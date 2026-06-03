from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeRunner


def test_app_config_exposes_feature_flags(app):
    with TestClient(app) as client:
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json()["features"]["image_input_enabled"] is False


def test_conversation_message_generation_flow(app):
    with TestClient(app) as client:
        created = client.post("/api/conversations", json={"title": "Test"}).json()
        conversation_id = created["id"]

        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "make a 40 mm cube with a 10 mm through-hole"},
        )
        assert response.status_code == 200
        generation_id = response.json()["generation"]["id"]

        generation = client.get(f"/api/generations/{generation_id}").json()
        assert generation["status"] == "succeeded"
        assert generation["artifacts"]["step"] is True
        assert generation["artifacts"]["glb"] is True
        assert generation["artifacts"]["script"] is True
        assert generation["artifacts"]["log"] is True

        detail = client.get(f"/api/conversations/{conversation_id}").json()
        assert len(detail["messages"]) == 2
        assert detail["messages"][-1]["role"] == "assistant"

        step = client.get(f"/api/generations/{generation_id}/artifacts/step")
        assert step.status_code == 200
        assert b"ISO-10303-21" in step.content

        events = client.get(f"/api/generations/{generation_id}/events")
        assert events.status_code == 200
        event_types = [event["event_type"] for event in events.json()]
        assert "status" in event_types
        assert "artifact" in event_types

        with client.websocket_connect(
            f"/api/generations/{generation_id}/stream"
        ) as websocket:
            first = websocket.receive_json()
            assert first["type"] == "event"
            while True:
                payload = websocket.receive_json()
                if payload["type"] == "done":
                    assert payload["generation"]["status"] == "succeeded"
                    break


def test_missing_conversation_returns_404(app):
    with TestClient(app) as client:
        response = client.get("/api/conversations/does-not-exist")
        assert response.status_code == 404


def test_image_upload_disabled_returns_403(app):
    with TestClient(app) as client:
        created = client.post("/api/conversations", json={"title": "Images"}).json()
        response = client.post(
            f"/api/conversations/{created['id']}/attachments/images?filename=part.png",
            content=b"png",
            headers={"content-type": "image/png"},
        )
        assert response.status_code == 403


def test_image_upload_and_message_attachment_flow(test_settings):
    settings = test_settings.model_copy(update={"image_input_enabled": True})
    with TestClient(create_app(settings=settings, runner=FakeRunner())) as client:
        created = client.post("/api/conversations", json={"title": "Images"}).json()
        conversation_id = created["id"]

        upload = client.post(
            f"/api/conversations/{conversation_id}/attachments/images?filename=part.png",
            content=b"fake png bytes",
            headers={"content-type": "image/png"},
        )
        assert upload.status_code == 200
        attachment = upload.json()
        assert attachment["filename"] == "part.png"
        assert attachment["content_type"] == "image/png"

        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={
                "content": "make this reference image into a bracket",
                "attachment_ids": [attachment["id"]],
            },
        )
        assert response.status_code == 200
        assert response.json()["message"]["attachments"][0]["id"] == attachment["id"]

        image = client.get(
            f"/api/conversations/{conversation_id}/attachments/images/{attachment['id']}"
        )
        assert image.status_code == 200
        assert image.content == b"fake png bytes"

        detail = client.get(f"/api/conversations/{conversation_id}").json()
        assert detail["messages"][0]["attachments"][0]["filename"] == "part.png"
