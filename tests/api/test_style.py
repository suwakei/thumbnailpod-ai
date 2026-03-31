import uuid
from unittest.mock import AsyncMock, patch

from app.schemas.style import StyleAnalyzeResponse, StyleMetadata, StyleTrainResponse, TrainPhase


def test_analyze_style_success(client, internal_headers, sample_user_id):
    expected = StyleAnalyzeResponse(
        style_metadata=StyleMetadata(
            color_palette=["#ff0000", "#00ff00", "#0000ff", "#ffffff", "#000000"],
            composition_features={"avg_aspect_ratio": 1.78, "image_count": 3},
            clip_embedding=[0.1] * 768,
        )
    )
    with patch("app.api.internal.style._analyzer") as mock:
        mock.analyze = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/style/analyze",
            json={
                "user_id": sample_user_id,
                "image_urls": [
                    "https://example.com/thumb1.jpg",
                    "https://example.com/thumb2.jpg",
                ],
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data["style_metadata"]["color_palette"]) == 5


def test_analyze_style_requires_auth(client, sample_user_id):
    response = client.post(
        "/internal/style/analyze",
        json={
            "user_id": sample_user_id,
            "image_urls": ["https://example.com/thumb.jpg"],
        },
    )
    assert response.status_code == 403


def test_analyze_style_empty_urls(client, internal_headers, sample_user_id):
    response = client.post(
        "/internal/style/analyze",
        json={"user_id": sample_user_id, "image_urls": []},
        headers=internal_headers,
    )
    assert response.status_code == 422


def test_train_style_enqueue_success(client, internal_headers, sample_user_id):
    style_model_id = str(uuid.uuid4())
    expected = StyleTrainResponse(
        style_model_id=style_model_id,
        job_id=str(uuid.uuid4()),
        phase=TrainPhase.STYLE_REF,
    )
    with patch("app.api.internal.style._trainer") as mock:
        mock.enqueue = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/style/train",
            json={
                "style_model_id": style_model_id,
                "user_id": sample_user_id,
                "image_urls": [f"https://example.com/thumb{i}.jpg" for i in range(10)],
                "phase": "style_ref",
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    assert response.json()["phase"] == "style_ref"


def test_train_style_too_few_images(client, internal_headers, sample_user_id):
    response = client.post(
        "/internal/style/train",
        json={
            "style_model_id": str(uuid.uuid4()),
            "user_id": sample_user_id,
            "image_urls": ["https://example.com/thumb.jpg"],  # min is 10
            "phase": "style_ref",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
