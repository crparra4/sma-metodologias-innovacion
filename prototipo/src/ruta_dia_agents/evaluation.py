"""Evaluación local sobre el runtime CrewAI real; no es un juez semántico automático."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import replace
from pathlib import Path

from crewai.llms.hooks.base import BaseInterceptor

from .audit import JsonlVerificationRecorder
from .config import PROJECT_ROOT, Settings
from .contracts import CandidateResponse, HandoffContract, ProjectState
from .knowledge import KnowledgeCatalog
from .runtime import CrewAIRuntime, build_llm
from .service import RutaDiaService


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def append_event(path: Path, value) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def structural_checks(case: dict, result: dict) -> dict[str, bool]:
    """Solo criterios mecánicos; pasar estos controles no demuestra fidelidad."""
    expected = case["expected"]
    if case["kind"] == "verify":
        return {
            "expected_verdict": result["verdict"] == expected["verdict"],
            "correct_source": result["source_tool_id"] == "cinco-porques",
        }
    checks = {
        "expected_stage": result["handoff"]["stage"] == expected["stage"],
        "expected_tool": result["handoff"]["active_tool"] == expected["active_tool"],
        "expected_degradation": result["degraded"] == expected["degraded"],
    }
    if "finding" in expected:
        checks["knowledge_gap"] = any(
            f["code"] == expected["finding"] for f in result["verification"]["findings"]
        )
    return checks


class WireRecorder(BaseInterceptor):
    """Registra cuerpos HTTP, nunca cabeceras ni claves. Uso secuencial y sin streaming."""

    def __init__(self, path: Path):
        self.path = path
        self.number = 0
        self.started = 0.0

    def on_outbound(self, message):
        self.number += 1
        self.started = time.perf_counter()
        append_event(
            self.path,
            {
                "event": "request",
                "number": self.number,
                "body": json.loads(message.content),
            },
        )
        return message

    def on_inbound(self, message):
        message.read()
        try:
            body = message.json()
        except ValueError:
            body = {"raw": message.text}
        append_event(
            self.path,
            {
                "event": "response",
                "number": self.number,
                "seconds": time.perf_counter() - self.started,
                "status": message.status_code,
                "body": body,
            },
        )
        return message


class MeasuredRuntime(CrewAIRuntime):
    def __init__(self, settings: Settings, output: Path):
        self.output = output
        self.calls = []
        recorder = WireRecorder(output / "http.jsonl")
        direct_llm = build_llm(
            settings,
            thinking=False,
            max_tokens=384,
            interceptor=recorder,
            top_p=0.8,
            additional_params={
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": False},
                    "cache_prompt": False,
                }
            },
        )
        verifier_llm = build_llm(
            settings,
            thinking=settings.thinking,
            max_tokens=1536 if settings.thinking else 384,
            interceptor=recorder,
            top_p=0.8,
            additional_params={
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": settings.thinking},
                    "cache_prompt": False,
                }
            },
        )
        super().__init__(settings, llm=direct_llm, verifier_llm=verifier_llm)
        for agent in (self.orchestrator, self.methodologist, self.verifier):
            # Un exceso de contexto debe quedar como error, no resumirse silenciosamente.
            agent.respect_context_window = False

    def _run(self, agent, description, output_model):
        start = time.perf_counter()
        call = {
            "role": agent.role,
            "contract": output_model.__name__,
            "description": description,
            "schema": output_model.model_json_schema(),
        }
        try:
            result = super()._run(agent, description, output_model)
            call.update(status="ok", output=result.model_dump(mode="json"))
            return result
        except Exception as exc:
            call.update(status="error", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            call["seconds"] = time.perf_counter() - start
            self.calls.append(call)
            append_event(self.output / "roles.jsonl", call)


def run_case(case: dict, settings: Settings, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    runtime = MeasuredRuntime(settings, output)
    catalog = KnowledgeCatalog(settings.route_path)
    catalog.require_valid()
    record = {
        "case_id": case["id"],
        "model": settings.model,
        "seed": settings.seed,
        "case": case,
        "review_status": "pending",
        "review_criteria": case["review_criteria"],
    }
    start = time.perf_counter()
    try:
        if case["kind"] == "turn":
            service = RutaDiaService(
                catalog, runtime, JsonlVerificationRecorder(output / "audit.jsonl")
            )
            state = ProjectState(notebook_id=f"eval-{case['id']}-{settings.seed}", **case["state"])
            result = service.handle_turn(case["message"], state)
        else:
            handoff = HandoffContract(
                intent="orientacion",
                phase="Descubrimiento",
                stage=1,
                expertise="novel",
                recommendations=[{"tool_id": "cinco-porques", "reason": "Analizar causas"}],
                active_tool="cinco-porques",
                context_summary="Prueba de fidelidad a la ficha",
            )
            result = runtime.verify(
                CandidateResponse.model_validate(case["candidate"]),
                handoff,
                catalog.tool_card("cinco-porques"),
                message=case.get("message", ""),
                state=ProjectState(**case.get("state", {})),
            )
        result_data = result.model_dump(mode="json")
        checks = structural_checks(case, result_data)
        record.update(
            status="ok", result=result_data, checks=checks, mechanical_pass=all(checks.values())
        )
    except Exception as exc:
        record.update(
            status="error", error_type=type(exc).__name__, error=str(exc), mechanical_pass=False
        )
    finally:
        record["seconds"] = time.perf_counter() - start
        record["role_calls"] = len(runtime.calls)
        write_json(output / "result.json", record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18083)
    args = parser.parse_args()
    cases = json.loads((PROJECT_ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
    case = next(c for c in cases["cases"] if c["id"] == args.case)
    settings = replace(
        Settings.from_env(),
        model=args.model,
        base_url=f"http://127.0.0.1:{args.port}/v1",
        api_key=os.environ["RUTA_DIA_EVAL_KEY"],
        temperature=0.7,
        max_tokens=1536 if Settings.from_env().thinking else 384,
        timeout=240,
        seed=args.seed,
        agent_max_retry_limit=0,
        verbose=False,
    )
    result = run_case(case, settings, args.output)
    print(
        json.dumps(
            {k: result[k] for k in ("case_id", "status", "seconds", "mechanical_pass")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
