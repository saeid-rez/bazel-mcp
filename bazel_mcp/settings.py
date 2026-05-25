"""Environment-driven configuration for Bazel MCP."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BazelMcpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAZEL_MCP_")

    bazel_path: str = "bazel"
    timeout: int = 300
    workspace_root: str | None = None
    max_output_chars: int = 32_000


@lru_cache
def get_settings() -> BazelMcpSettings:
    return BazelMcpSettings()
