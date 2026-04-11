import uuid
from unittest.mock import AsyncMock, patch

from app.schemas.job import JobStatus, JobStatusResponse


def test_get_job_status_completed(client, internal_headers, sample_job_id):
    expected = JobStatusResponse(
        job_id=sample_job_id,
        status=JobStatus.COMPLETED,
        result={"s3_key": f"thumbnails/user/{sample_job_id}.png"},
    )
    with patch("app.api.internal.jobs.get_job_status", AsyncMock(return_value=expected)):
        response = client.get(f"/internal/jobs/{sample_job_id}", headers=internal_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_get_job_status_pending(client, internal_headers, sample_job_id):
    expected = JobStatusResponse(job_id=sample_job_id, status=JobStatus.PENDING)
    with patch("app.api.internal.jobs.get_job_status", AsyncMock(return_value=expected)):
        response = client.get(f"/internal/jobs/{sample_job_id}", headers=internal_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_get_job_status_failed(client, internal_headers, sample_job_id):
    expected = JobStatusResponse(
        job_id=sample_job_id,
        status=JobStatus.FAILED,
        error_message="DALL-E API rate limit exceeded",
    )
    with patch("app.api.internal.jobs.get_job_status", AsyncMock(return_value=expected)):
        response = client.get(f"/internal/jobs/{sample_job_id}", headers=internal_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "rate limit" in data["error_message"]


def test_get_job_not_found(client, internal_headers):
    from fastapi import HTTPException  # noqa: PLC0415

    with patch(
        "app.api.internal.jobs.get_job_status",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Job not found")),
    ):
        response = client.get(f"/internal/jobs/{uuid.uuid4()}", headers=internal_headers)
    assert response.status_code == 404


def test_get_job_requires_auth(client, sample_job_id):
    response = client.get(f"/internal/jobs/{sample_job_id}")
    assert response.status_code == 403
