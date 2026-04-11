from unittest.mock import AsyncMock, patch

from app.schemas.edit import EditResponse


def test_edit_success(client, internal_headers, sample_job_id, sample_user_id):
    expected = EditResponse(
        job_id=sample_job_id,
        layers={
            "text_layer": f"edited/{sample_job_id}/text_layer.png",
            "composite": f"edited/{sample_job_id}/composite.png",
        },
        unchanged_layers=["background_layer", "person_layer", "effect_layer"],
    )
    with patch("app.api.internal.edit._editor") as mock:
        mock.edit = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/edit",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "original_layers": {
                    "text_layer": f"layers/{sample_job_id}/text_layer.png",
                    "background_layer": f"layers/{sample_job_id}/background_layer.png",
                    "person_layer": f"layers/{sample_job_id}/person_layer.png",
                    "effect_layer": f"layers/{sample_job_id}/effect_layer.png",
                },
                "operations": [
                    {
                        "type": "text_change",
                        "layer": "text_layer",
                        "content": "New Title",
                        "position": {"x": 100, "y": 50},
                    }
                ],
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == sample_job_id
    assert "text_layer" in data["layers"]
    assert "composite" in data["layers"]
    assert "background_layer" in data["unchanged_layers"]


def test_edit_color_adjust(client, internal_headers, sample_job_id, sample_user_id):
    expected = EditResponse(
        job_id=sample_job_id,
        layers={
            "background_layer": f"edited/{sample_job_id}/background_layer.png",
            "composite": f"edited/{sample_job_id}/composite.png",
        },
        unchanged_layers=["text_layer", "person_layer"],
    )
    with patch("app.api.internal.edit._editor") as mock:
        mock.edit = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/edit",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "original_layers": {
                    "background_layer": f"layers/{sample_job_id}/background_layer.png",
                    "text_layer": f"layers/{sample_job_id}/text_layer.png",
                    "person_layer": f"layers/{sample_job_id}/person_layer.png",
                },
                "operations": [
                    {
                        "type": "color_adjust",
                        "layer": "background_layer",
                        "brightness": 1.2,
                    }
                ],
            },
            headers=internal_headers,
        )
    assert response.status_code == 200


def test_edit_requires_auth(client, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/edit",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "original_layers": {"text_layer": "layers/text.png"},
            "operations": [
                {"type": "text_change", "layer": "text_layer", "content": "Hi"}
            ],
        },
    )
    assert response.status_code == 403


def test_edit_empty_operations(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/edit",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "original_layers": {"text_layer": "layers/text.png"},
            "operations": [],
        },
        headers=internal_headers,
    )
    assert response.status_code == 422


def test_edit_invalid_operation_type(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/edit",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "original_layers": {"text_layer": "layers/text.png"},
            "operations": [
                {"type": "invalid_op", "layer": "text_layer"}
            ],
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
