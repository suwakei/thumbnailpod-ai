from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "development"

    # OpenAI / DALL-E
    openai_api_key: str = ""

    # AWS
    aws_region: str = "ap-northeast-1"
    s3_bucket: str = ""
    sqs_queue_url: str = ""

    # Database (for job status updates)
    database_url: str = ""

    # Internal service auth (shared secret with Go API)
    internal_api_secret: str = ""

    # AI model settings
    sd_model_id: str = "stabilityai/stable-diffusion-xl-base-1.0"
    clip_model_id: str = "openai/clip-vit-large-patch14"
    sam_model_checkpoint: str = "sam_vit_h_4b8939.pth"

    # Generation defaults
    image_width: int = 1280
    image_height: int = 720

    # Image download safety (SSRF / DoS mitigation)
    # Hosts whose https URLs are allowed as image sources. Suffix match on the
    # URL hostname (case-insensitive). Defaults cover YouTube thumbnails and
    # S3 presigned URLs. Override via ALLOWED_IMAGE_HOST_SUFFIXES env var as
    # a comma-separated list.
    allowed_image_host_suffixes: str = (
        "ytimg.com,googleusercontent.com,amazonaws.com,blob.core.windows.net"
    )
    # Maximum bytes to read from a remote image URL before aborting.
    max_image_download_bytes: int = 20 * 1024 * 1024
    # Maximum pixel count for PIL decoding (decompression bomb guard).
    max_image_pixels: int = 50_000_000


settings = Settings()
