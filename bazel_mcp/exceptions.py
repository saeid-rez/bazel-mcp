"""Custom exceptions for Bazel MCP."""


class BazelMcpError(Exception):
    """Base exception for Bazel MCP."""


class BazelNotFoundError(BazelMcpError):
    """Bazel binary not found on PATH or at configured path."""


class BazelExecutionError(BazelMcpError):
    """Bazel command returned a non-zero exit code."""

    def __init__(self, message: str, *, return_code: int, stderr: str) -> None:
        super().__init__(message)
        self.return_code = return_code
        self.stderr = stderr

    def __str__(self) -> str:
        base = super().__str__()
        if self.stderr and self.stderr.strip():
            return f"{base}\n{self.stderr.strip()}"
        return base


class WorkspaceNotFoundError(BazelMcpError):
    """No Bazel workspace marker found."""

    def __init__(self, message: str, *, searched_paths: list[str] | None = None) -> None:
        super().__init__(message)
        self.searched_paths = searched_paths or []
