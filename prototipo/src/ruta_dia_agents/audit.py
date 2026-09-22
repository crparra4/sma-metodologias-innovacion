from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .contracts import CandidateResponse, HandoffContract, VerificationResult


class VerificationRecorder(Protocol):
    def record(
        self,
        notebook_id: str,
        attempt: int,
        handoff: HandoffContract,
        candidate: CandidateResponse,
        verification: VerificationResult,
    ) -> None: ...


class NullRecorder:
    def record(
        self,
        notebook_id: str,
        attempt: int,
        handoff: HandoffContract,
        candidate: CandidateResponse,
        verification: VerificationResult,
    ) -> None:
        return None


class JsonlVerificationRecorder:
    def __init__(self, path: Path):
        self.path = Path(path)

    def record(
        self,
        notebook_id: str,
        attempt: int,
        handoff: HandoffContract,
        candidate: CandidateResponse,
        verification: VerificationResult,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "notebook_id": notebook_id,
            "attempt": attempt,
            "handoff": handoff.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

