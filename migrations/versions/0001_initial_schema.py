"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("youtube_channel_id", sa.String(64), unique=True, nullable=False),
        sa.Column("channel_name", sa.String(255), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "creator", "pro", "business", name="plan_enum"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("generation_count_month", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------------------------
    # style_models
    # ------------------------------------------------------------------
    op.create_table(
        "style_models",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.Enum("style_ref", "lora", name="style_model_type_enum"),
            nullable=False,
            server_default="style_ref",
        ),
        sa.Column("s3_key", sa.String(512), nullable=True),
        sa.Column("style_metadata", JSONB, nullable=True),
        sa.Column("source_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("pending", "training", "ready", "failed", name="style_model_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_style_models_user_id", "style_models", ["user_id"])

    # ------------------------------------------------------------------
    # generation_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "generation_jobs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "style_model_id",
            UUID,
            sa.ForeignKey("style_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="job_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_generation_jobs_user_id", "generation_jobs", ["user_id"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    # ------------------------------------------------------------------
    # generated_thumbnails
    # ------------------------------------------------------------------
    op.create_table(
        "generated_thumbnails",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "job_id",
            UUID,
            sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("psd_s3_key", sa.String(512), nullable=True),
        sa.Column("width", sa.Integer, nullable=False, server_default="1280"),
        sa.Column("height", sa.Integer, nullable=False, server_default="720"),
        sa.Column("applied_to_video_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_generated_thumbnails_job_id", "generated_thumbnails", ["job_id"])

    # ------------------------------------------------------------------
    # thumbnail_layers
    # ------------------------------------------------------------------
    op.create_table(
        "thumbnail_layers",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "thumbnail_id",
            UUID,
            sa.ForeignKey("generated_thumbnails.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_thumbnail_layers_thumbnail_id", "thumbnail_layers", ["thumbnail_id"])


def downgrade() -> None:
    op.drop_table("thumbnail_layers")
    op.drop_table("generated_thumbnails")
    op.drop_table("generation_jobs")
    op.drop_table("style_models")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
    op.execute("DROP TYPE IF EXISTS style_model_status_enum")
    op.execute("DROP TYPE IF EXISTS style_model_type_enum")
    op.execute("DROP TYPE IF EXISTS plan_enum")
