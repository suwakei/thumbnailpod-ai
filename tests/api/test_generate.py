from unittest.mock import AsyncMock, patch

from app.schemas.generate import GenerateResponse


def test_generate_dalle_success(client, internal_headers, sample_job_id, sample_user_id):
    expected = GenerateResponse(
        job_id=sample_job_id,
        s3_key=f"thumbnails/{sample_user_id}/{sample_job_id}.png",
        width=1280,
        height=720,
    )
    with patch("app.api.internal.generate._dalle") as mock:
        mock.generate = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/generate",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "prompt": "YouTube thumbnail for a cooking channel",
                "engine": "dalle3",
            },
            headers=internal_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == sample_job_id
    assert data["width"] == 1280


def test_generate_sdxl_success(client, internal_headers, sample_job_id, sample_user_id):
    expected = GenerateResponse(
        job_id=sample_job_id,
        s3_key=f"thumbnails/{sample_user_id}/{sample_job_id}.png",
        width=1280,
        height=720,
    )
    with patch("app.api.internal.generate._sdxl") as mock:
        mock.generate = AsyncMock(return_value=expected)
        response = client.post(
            "/internal/generate",
            json={
                "job_id": sample_job_id,
                "user_id": sample_user_id,
                "prompt": "Epic gaming thumbnail",
                "engine": "sdxl",
            },
            headers=internal_headers,
        )
    assert response.status_code == 200


def test_generate_requires_auth(client, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/generate",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "prompt": "test",
        },
    )
    assert response.status_code == 403


def test_generate_invalid_engine(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/generate",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "prompt": "test",
            "engine": "unknown_engine",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422


def test_generate_empty_prompt(client, internal_headers, sample_job_id, sample_user_id):
    response = client.post(
        "/internal/generate",
        json={
            "job_id": sample_job_id,
            "user_id": sample_user_id,
            "prompt": "",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
