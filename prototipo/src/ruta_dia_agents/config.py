from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


@dataclass(frozen=True)
class Settings:
    model: str
    verbose: bool
    route_path: Path
    audit_path: Path
    memory_path: Path
    checkpoint_path: Path
    base_url: str | None = None
    api_key: str | None = field(default=None, repr=False)
    temperature: float = 0
    max_tokens: int | None = None
    timeout: float = 240
    seed: int | None = None
    agent_max_retry_limit: int = 2
    top_p: float | None = None
    thinking: bool = False
    runtime: str = "langgraph"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")
        local_root = Path(os.getenv("LOCALAPPDATA", str(PROJECT_ROOT / "data"))) / "RutaDIA"
        data_root = Path(os.getenv("RUTA_DIA_DATA_DIR", str(local_root))).expanduser()
        return cls(
            model=os.getenv("RUTA_DIA_MODEL", "gemini/gemini-3.6-flash"),
            verbose=_as_bool(os.getenv("RUTA_DIA_VERBOSE")),
            route_path=PROJECT_ROOT / "knowledge" / "routes" / "ruta-dia.json",
            audit_path=PROJECT_ROOT / "data" / "verifications.jsonl",
            memory_path=data_root / "notebooks.sqlite3",
            checkpoint_path=data_root / "checkpoints.sqlite3",
            base_url=os.getenv("RUTA_DIA_BASE_URL") or None,
            api_key=os.getenv("RUTA_DIA_API_KEY") or None,
            temperature=float(os.getenv("RUTA_DIA_TEMPERATURE", "0")),
            max_tokens=(
                int(os.environ["RUTA_DIA_MAX_TOKENS"]) if os.getenv("RUTA_DIA_MAX_TOKENS") else None
            ),
            timeout=float(os.getenv("RUTA_DIA_TIMEOUT", "240")),
            seed=int(os.environ["RUTA_DIA_SEED"]) if os.getenv("RUTA_DIA_SEED") else None,
            top_p=float(os.environ["RUTA_DIA_TOP_P"]) if os.getenv("RUTA_DIA_TOP_P") else None,
            agent_max_retry_limit=int(os.getenv("RUTA_DIA_AGENT_RETRIES", "2")),
            thinking=_as_bool(os.getenv("RUTA_DIA_THINKING")),
            runtime=os.getenv("RUTA_DIA_RUNTIME", "langgraph").strip().lower(),
        )
