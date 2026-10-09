"""Background job orchestration using Redis as a job store.

Provides a lightweight job tracking system that records job status, progress,
and results. Jobs are stored as Redis hashes with a predictable key pattern:

    job:{job_id}  ->  {status, created_at, started_at, completed_at,
                      total, succeeded, failed, error, result_ref}

This avoids a hard dependency on Celery for job tracking while remaining
compatible with a future Celery migration.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from db.redis_client import redis_client

logger = logging.getLogger(__name__)

JOB_PREFIX = "job"
JOB_TTL = 86400  # Keep job records for 24 hours


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _job_key(job_id: str) -> str:
    return f"{JOB_PREFIX}:{job_id}"


async def create_job(
    job_type: str,
    entity_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a new job record and return its ID."""
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    data: dict[str, Any] = {
        "job_id": job_id,
        "job_type": job_type,
        "entity_id": entity_id or "",
        "status": JobStatus.QUEUED,
        "created_at": now,
        "started_at": "",
        "completed_at": "",
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "error": "",
        "result_ref": "",
    }
    if extra:
        data.update(extra)

    try:
        await redis_client.set_json(_job_key(job_id), data, ttl=JOB_TTL)
    except Exception as exc:
        logger.warning("Redis unavailable, job tracking disabled", extra={"job_id": job_id, "error": str(exc)})
    logger.info("Job created", extra={"job_id": job_id, "job_type": job_type, "entity_id": entity_id})
    return job_id


async def get_job(job_id: str) -> dict[str, Any] | None:
    """Retrieve job status/details."""
    try:
        data = await redis_client.get_json(_job_key(job_id))
        if data is None:
            return None
        return data
    except Exception as exc:
        logger.warning("Redis unavailable, cannot retrieve job", extra={"job_id": job_id, "error": str(exc)})
        return None


async def update_job_status(job_id: str, status: str, **extra: Any) -> None:
    """Update a job's status and optional extra fields."""
    try:
        data = await redis_client.get_json(_job_key(job_id))
        if data is None:
            return
        data["status"] = status
        now = datetime.utcnow().isoformat()
        if status == JobStatus.RUNNING and not data.get("started_at"):
            data["started_at"] = now
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            data["completed_at"] = now
        for k, v in extra.items():
            data[k] = v
        await redis_client.set_json(_job_key(job_id), data, ttl=JOB_TTL)
    except Exception as exc:
        logger.warning("Redis unavailable, job status update skipped", extra={"job_id": job_id, "error": str(exc)})
        return
    logger.info("Job status updated", extra={"job_id": job_id, "status": status})


async def set_job_progress(
    job_id: str, *, succeeded: int | None = None, failed: int | None = None, total: int | None = None
) -> None:
    """Update job progress counters."""
    data = await redis_client.get_json(_job_key(job_id))
    if data is None:
        return

    if total is not None:
        data["total"] = total
    if succeeded is not None:
        data["succeeded"] = succeeded
    if failed is not None:
        data["failed"] = failed

    await redis_client.set_json(_job_key(job_id), data, ttl=JOB_TTL)


async def cancel_job(job_id: str) -> bool:
    """Cancel a queued or running job."""
    data = await redis_client.get_json(_job_key(job_id))
    if data is None:
        return False

    current_status = data.get("status")
    if current_status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        return False

    await update_job_status(job_id, JobStatus.CANCELLED)
    return True


async def delete_job(job_id: str) -> None:
    """Remove a job record."""
    await redis_client.delete(_job_key(job_id))
