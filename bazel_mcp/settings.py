"""Runtime configuration for Bazel MCP."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class BazelMcpSettings:
    bazel_path: str = "bazel"
    timeout: int = 300
    workspace_root: str | None = None
    max_output_chars: int = 32_000


_settings = BazelMcpSettings()


def get_settings() -> BazelMcpSettings:
    return _settings


def configure_settings(
    *,
    bazel_path: str | None = None,
    timeout: int | None = None,
    workspace_root: str | None = None,
    max_output_chars: int | None = None,
) -> None:
    """Update process-local settings from CLI arguments."""
    global _settings

    updates = {}
    if bazel_path is not None:
        updates["bazel_path"] = bazel_path
    if timeout is not None:
        updates["timeout"] = timeout
    if workspace_root is not None:
        updates["workspace_root"] = workspace_root
    if max_output_chars is not None:
        updates["max_output_chars"] = max_output_chars

    _settings = replace(_settings, **updates)


def reset_settings() -> None:
    """Restore defaults. Intended for tests."""
    global _settings
    _settings = BazelMcpSettings()
