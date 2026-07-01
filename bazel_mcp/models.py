"""Pydantic models for tool inputs and outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class BazelBuildDiagnostic(BaseModel):
    file: str | None = None
    line: int | None = None
    col: int | None = None
    severity: Literal["error", "warning", "info"] = "error"
    message: str
    target: str | None = None


class BazelBuildResult(BaseModel):
    success: bool
    exit_code: int
    duration_seconds: float
    summary: str
    failed_targets: list[str] = Field(default_factory=list)
    errors: list[BazelBuildDiagnostic] = Field(default_factory=list)
    warnings: list[BazelBuildDiagnostic] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


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
