from fastapi.testclient import TestClient


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


def test_missing_conversation_returns_404(app):
    with TestClient(app) as client:
        response = client.get("/api/conversations/does-not-exist")
        assert response.status_code == 404
