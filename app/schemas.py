from __future__ import annotations

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scan_path: str = Field(min_length=1, max_length=4096)
    notes: str = Field(default="", max_length=2000)


class ReviewJob(BaseModel):
    job_id: str
    name: str
    scan_path: str
    status: str
    total_items: int
    reviewed_items: int
    notes: str
    created_at: str
    updated_at: str


class ReviewItem(BaseModel):
    item_id: str
    job_id: str
    original_path: str
    folder_path: str
    file_name: str
    file_size: int
    extension: str
    file_mtime: str
    duration_seconds: float | None
    resolution: str
    codec: str
    review_status: str
    suggested_action: str
    user_action: str
    user_notes: str
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    jobs: list[ReviewJob]


class JobDetailResponse(BaseModel):
    job: ReviewJob
    items: list[ReviewItem]
