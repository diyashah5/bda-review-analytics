from fastapi.testclient import TestClient

from api import main


client = TestClient(main.app)


def test_prediction_returns_normalized_probabilities(monkeypatch):
    monkeypatch.setattr(
        main,
        "model_artifacts",
        lambda: (
            {"negative": 0.0, "neutral": 0.0, "positive": 0.0},
            {"good": (1.0, -1.0, 0.0, 2.0)},
        ),
    )

    response = client.post("/predict/sentiment", json={"text": "good"})

    assert response.status_code == 200
    assert response.json()["sentiment"] == "positive"
    assert sum(response.json()["probabilities"].values()) == 1.0


def test_prediction_rejects_text_unknown_to_model(monkeypatch):
    monkeypatch.setattr(
        main,
        "model_artifacts",
        lambda: (
            {"negative": 0.0, "neutral": 0.0, "positive": 0.0},
            {},
        ),
    )

    response = client.post("/predict/sentiment", json={"text": "unseenword"})

    assert response.status_code == 422
    assert "No words" in response.json()["detail"]


def test_prediction_rejects_empty_review():
    response = client.post("/predict/sentiment", json={"text": " "})

    assert response.status_code == 422