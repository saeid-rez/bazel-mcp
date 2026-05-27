"""Parse bazel test stdout into structured results."""

from __future__ import annotations

import re
from pathlib import Path

from bazel_mcp.models import BazelTestResult, BazelTestTargetResult

_TEST_LINE = re.compile(
    r"^(?P<target>(?:@[\w\-]+)?//[\S]+)\s+(?P<status>PASSED|FAILED|FLAKY|TIMEOUT|SKIPPED)"
    r"(?:\s+in\s+(?P<duration>[\d.]+)s)?",
    re.MULTILINE,
)
_LOG_PATH = re.compile(
    r"(?:stdout|stderr|test\.log).*?:\s*(?P<path>\S+test\.log\S*)",
    re.IGNORECASE,
)
_BARE_LOG_PATH = re.compile(
    r"^\s+(?P<path>\S*testlogs/\S+/test\.log\S*)\s*$",
    re.MULTILINE,
)


def _find_log_paths(output: str) -> list[str]:
    matches = [
        (match.start(), match.group("path"))
        for pattern in (_LOG_PATH, _BARE_LOG_PATH)
        for match in pattern.finditer(output)
    ]
    return [path for _, path in sorted(matches, key=lambda item: item[0])]


def _read_log_excerpt(log_path: str, max_chars: int = 4000) -> str | None:
    path = Path(log_path.strip().strip('"'))
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(content) <= max_chars:
        return content
    keep = max_chars // 2
    return content[:keep] + "\n...[truncated]...\n" + content[-keep:]


def parse_bazel_test_output(
    stdout: str,
    stderr: str,
    return_code: int,
    *,
    workspace: Path | None = None,
) -> BazelTestResult:
    combined = stdout + "\n" + stderr
    targets: list[BazelTestTargetResult] = []
    log_paths = _find_log_paths(combined)
    log_index = 0

    for match in _TEST_LINE.finditer(combined):
        status = match.group("status")
        duration_raw = match.group("duration")
        duration = float(duration_raw) if duration_raw else None
        log_excerpt: str | None = None
        if status in ("FAILED", "FLAKY", "TIMEOUT") and log_index < len(log_paths):
            log_path = log_paths[log_index]
            if workspace and not Path(log_path).is_absolute():
                log_path = str(workspace / log_path)
            log_excerpt = _read_log_excerpt(log_path)
            log_index += 1

        targets.append(
            BazelTestTargetResult(
                target=match.group("target"),
                status=status,
                duration_seconds=duration,
                log_excerpt=log_excerpt,
            )
        )

    passed = sum(1 for t in targets if t.status == "PASSED")
    failed = sum(1 for t in targets if t.status in ("FAILED", "FLAKY", "TIMEOUT"))
    summary = f"{passed} passed, {failed} failed, {len(targets)} total"
    if not targets:
        summary = "No per-target summary lines parsed; see raw output."

    return BazelTestResult(
        exit_code=return_code,
        summary=summary,
        targets=targets,
        stdout=stdout,
        stderr=stderr,
    )
