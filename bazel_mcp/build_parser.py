"""Parse bazel build output into structured diagnostics."""

from __future__ import annotations

import re

from bazel_mcp.models import BazelBuildDiagnostic, BazelBuildResult

_MAX_ERRORS = 20
_MAX_WARNINGS = 20

_COMPILER_DIAGNOSTIC = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<col>\d+))?:\s+"
    r"(?P<severity>fatal error|error|warning):\s+(?P<message>.+)$",
    re.MULTILINE,
)
_BAZEL_ERROR = re.compile(
    r"^ERROR:\s+(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+(?P<message>.+)$",
    re.MULTILINE,
)
_TARGET_FAILED = re.compile(
    r"\bTarget\s+(?P<target>(?:@[\w.-]+)?//\S+)\s+failed to build\b",
    re.IGNORECASE,
)
_ACTION_TARGET_FAILED = re.compile(
    r"\b(?:Compiling|Linking|Building|Executing)\s+"
    r"(?P<target>(?:@[\w.-]+)?//\S+)\s+failed\b",
    re.IGNORECASE,
)
_SUMMARY = re.compile(
    r"^(?P<summary>(?:FAILED|INFO|ERROR):\s+Build\s+"
    r"(?:completed successfully|did NOT complete successfully|failed)[^\r\n]*)",
    re.MULTILINE,
)
_TARGET_LABEL = re.compile(r"(?P<target>(?:@[\w.-]+)?//[^\s,]+)")


def _clean_target(target: str) -> str:
    return target.rstrip(":.;)")


def _extract_target(text: str) -> str | None:
    match = _TARGET_LABEL.search(text)
    if not match:
        return None
    return _clean_target(match.group("target"))


def _append_unique(items: list[str], item: str | None) -> None:
    if item and item not in items:
        items.append(item)


def _normalize_severity(severity: str) -> str:
    if severity == "warning":
        return "warning"
    return "error"


def parse_bazel_build_output(
    stdout: str,
    stderr: str,
    return_code: int,
    *,
    duration: float = 0.0,
) -> BazelBuildResult:
    """Parse Bazel build output into a structured result."""
    combined = stderr + "\n" + stdout
    diagnostics: list[tuple[int, BazelBuildDiagnostic]] = []
    failed_targets: list[str] = []

    for match in _BAZEL_ERROR.finditer(combined):
        message = match.group("message").strip()
        action_failure = _ACTION_TARGET_FAILED.search(message)
        if action_failure:
            _append_unique(failed_targets, _clean_target(action_failure.group("target")))
            continue

        target = _extract_target(message)
        _append_unique(failed_targets, target)
        diagnostics.append(
            (
                match.start(),
                BazelBuildDiagnostic(
                    file=match.group("file").strip(),
                    line=int(match.group("line")),
                    col=int(match.group("col")),
                    severity="error",
                    message=message,
                    target=target,
                ),
            )
        )

    for match in _COMPILER_DIAGNOSTIC.finditer(combined):
        diagnostics.append(
            (
                match.start(),
                BazelBuildDiagnostic(
                    file=match.group("file").strip(),
                    line=int(match.group("line")),
                    col=int(match.group("col")) if match.group("col") else None,
                    severity=_normalize_severity(match.group("severity")),
                    message=match.group("message").strip(),
                ),
            )
        )

    ordered_diagnostics = [item for _, item in sorted(diagnostics, key=lambda entry: entry[0])]
    errors = [item for item in ordered_diagnostics if item.severity == "error"]
    warnings = [item for item in ordered_diagnostics if item.severity == "warning"]

    for pattern in (_TARGET_FAILED, _ACTION_TARGET_FAILED):
        for match in pattern.finditer(combined):
            _append_unique(failed_targets, _clean_target(match.group("target")))

    summary_match = _SUMMARY.search(combined)
    if summary_match:
        summary = summary_match.group("summary").strip()
    elif return_code == 0:
        summary = "Build completed successfully."
    else:
        summary = "Build failed."

    return BazelBuildResult(
        success=return_code == 0,
        exit_code=return_code,
        duration_seconds=duration,
        summary=summary,
        failed_targets=failed_targets,
        errors=errors[:_MAX_ERRORS],
        warnings=warnings[:_MAX_WARNINGS],
        stdout=stdout,
        stderr=stderr,
    )
