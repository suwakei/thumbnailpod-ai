from unittest.mock import AsyncMock, patch

from app.schemas.psd import PSDBuildResponse


def test_psd_build_success(client, internal_headers, sample_job_id, sample_user_id):
    expected = PSDBuildResponse(
        job_id=sample_job_id,
        psd_s3_key=f"thumbnails/{sample_user_id}/{sample_job_id}.psd",
    )
    with patch("app.api.internal.psd._builder") as mock:
        mock.build_from_layers = AsyncMock(return_value=expected.psd_s3_key)
        response = client.post(
            "/internal/psd",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "base_image_url": "https://example.com/base.png",
                "layers": [
                    {"label": "background", "s3_key": f"layers/{sample_job_id}/background.png"},
                    {"label": "person", "s3_key": f"layers/{sample_job_id}/person.png"},
                    {"label": "text_region", "s3_key": f"layers/{sample_job_id}/text_region.png"},
                ],
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == sample_job_id
    assert data["psd_s3_key"].endswith(".psd")


def test_psd_build_requires_auth(client, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/psd",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "base_image_url": "https://example.com/base.png",
            "layers": [
                {"label": "background", "s3_key": "layers/bg.png"},
            ],
        },
    )
    assert response.status_code == 403


def test_psd_build_invalid_url(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/psd",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "base_image_url": "not-a-url",
            "layers": [
                {"label": "background", "s3_key": "layers/bg.png"},
            ],
        },
        headers=internal_headers,
    )
    assert response.status_code == 422


def test_psd_build_missing_layers(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/psd",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "base_image_url": "https://example.com/base.png",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
