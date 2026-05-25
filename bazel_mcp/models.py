"""Pydantic models for tool inputs and outputs."""

from pydantic import BaseModel, Field


class BazelTestTargetResult(BaseModel):
    target: str
    status: str
    duration_seconds: float | None = None
    log_excerpt: str | None = None


class BazelTestResult(BaseModel):
    exit_code: int
    summary: str
    targets: list[BazelTestTargetResult] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
