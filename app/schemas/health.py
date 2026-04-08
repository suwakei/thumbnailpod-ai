from pydantic import BaseModel


class ServiceHealth(BaseModel):
    status: str
    latency_ms: float | None = None


class GpuInfo(BaseModel):
    available: bool
    device_name: str | None = None
    memory_total_gb: float | None = None
    memory_used_gb: float | None = None


class SystemInfo(BaseModel):
    python_version: str
    cpu_percent: float | None = None
    memory_percent: float | None = None


class HealthDetailResponse(BaseModel):
    status: str
    version: str
    services: dict[str, ServiceHealth]
    gpu: GpuInfo
    system: SystemInfo
    checked_at: str
