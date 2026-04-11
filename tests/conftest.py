import os
import uuid

import pytest
from fastapi.testclient import TestClient

# Set required env vars before importing app
os.environ.setdefault("INTERNAL_API_SECRET", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("SQS_QUEUE_URL", "http://localhost:4566/test/queue")


@pytest.fixture(scope="session")
def client():
    from app.main import app  # noqa: PLC0415

    return TestClient(app)


@pytest.fixture
def internal_headers():
    return {"X-Internal-Secret": "test-secret"}


@pytest.fixture
def sample_job_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_user_id():
    return str(uuid.uuid4())
