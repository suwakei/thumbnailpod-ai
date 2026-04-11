from unittest.mock import AsyncMock, patch

from app.schemas.segment import Layer, SegmentResponse


def test_segment_success(client, internal_headers, sample_job_id):
    expected = SegmentResponse(
        job_id=sample_job_id,
        layers=[
            Layer(label="background", s3_key=f"layers/{sample_job_id}/background.png"),
            Layer(label="person", s3_key=f"layers/{sample_job_id}/person.png"),
            Layer(label="text_region", s3_key=f"layers/{sample_job_id}/text_region.png"),
        ],
    )
    with patch("app.api.internal.segment._segment") as mock:
        mock.segment = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/segment",
            json={
                "job_id": sample_job_id,
                "image_url": "https://example.com/thumbnail.png",
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == sample_job_id
    assert len(data["layers"]) == 3
    assert data["layers"][0]["label"] == "background"


def test_segment_requires_auth(client, sample_job_id):
    response = client.post(
        "/internal/segment",
        json={
            "job_id": sample_job_id,
            "image_url": "https://example.com/thumbnail.png",
        },
    )
    assert response.status_code == 403


def test_segment_invalid_url(client, internal_headers, sample_job_id):
    response = client.post(
        "/internal/segment",
        json={
            "job_id": sample_job_id,
            "image_url": "not-a-url",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422


def test_segment_missing_job_id(client, internal_headers):
    response = client.post(
        "/internal/segment",
        json={
            "image_url": "https://example.com/thumbnail.png",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
