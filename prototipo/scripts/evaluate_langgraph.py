"""Ejecuta los casos de Ruta DIA con LangGraph y el modelo local ya iniciado."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from ruta_dia_agents.audit import JsonlVerificationRecorder
from ruta_dia_agents.config import PROJECT_ROOT, Settings
from ruta_dia_agents.contracts import CandidateResponse, HandoffContract, ProjectState
from ruta_dia_agents.direct_runtime import DirectOpenAIRuntime
from ruta_dia_agents.evaluation import structural_checks, write_json
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.langgraph_workflow import LangGraphRutaDia


def run_case(case: dict, settings: Settings, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    runtime = DirectOpenAIRuntime(settings)
    catalog = KnowledgeCatalog(settings.route_path)
    record = {
        "case_id": case["id"],
        "runtime": "langgraph",
        "model": settings.model,
        "seed": settings.seed,
        "case": case,
        "review_status": "pending",
    }
    started = time.perf_counter()
    try:
        if case["kind"] == "turn":
            workflow = LangGraphRutaDia(
                catalog,
                runtime,
                JsonlVerificationRecorder(output / "audit.jsonl"),
            )
            state = ProjectState(
                notebook_id=f"langgraph-{case['id']}-{settings.seed}",
                **case["state"],
            )
            result = workflow.handle_turn(case["message"], state)
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
        data = result.model_dump(mode="json")
        checks = structural_checks(case, data)
        record.update(
            status="ok",
            result=data,
            checks=checks,
            mechanical_pass=all(checks.values()),
        )
    except Exception as exc:
        record.update(
            status="error",
            error_type=type(exc).__name__,
            error=str(exc),
            mechanical_pass=False,
        )
    record["seconds"] = time.perf_counter() - started
    record["role_calls"] = len(runtime.calls)
    record["calls"] = runtime.calls
    write_json(output / "result.json", record)
    return record


def write_summary(root: Path, records: list[dict]) -> None:
    lines = [
        "# Evaluación LangGraph con Qwen local",
        "",
        "| Semilla | Caso | Estado | Segundos | Control mecánico | Llamadas |",
        "|---:|---|---|---:|---|---:|",
    ]
    for record in sorted(records, key=lambda item: (item["seed"], item["case_id"])):
        lines.append(
            f"| {record['seed']} | {record['case_id']} | {record['status']} | "
            f"{record['seconds']:.2f} | {record['mechanical_pass']} | "
            f"{record['role_calls']} |"
        )
    passed = sum(record["mechanical_pass"] for record in records)
    lines.extend(["", f"Resultado: **{passed}/{len(records)}** controles mecánicos.", ""])
    (root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(root / "summary.json", records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43])
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["F01", "G01", "V01", "V02", "V03", "V04", "V05", "F02"],
    )
    args = parser.parse_args()
    suite = json.loads((PROJECT_ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in suite["cases"]}
    unknown = set(args.cases) - set(cases)
    if unknown:
        raise ValueError(f"Casos inexistentes: {', '.join(sorted(unknown))}")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = PROJECT_ROOT / "data" / "evaluations" / f"{stamp}-langgraph"
    root.mkdir(parents=True, exist_ok=False)
    records = []
    for seed in args.seeds:
        settings = replace(Settings.from_env(), seed=seed, runtime="langgraph")
        for case_id in args.cases:
            print(f"RUN LangGraph seed={seed} case={case_id}", flush=True)
            record = run_case(
                case=cases[case_id],
                settings=settings,
                output=root / f"seed-{seed}" / case_id,
            )
            records.append(record)
            print(
                f"DONE {case_id}: {record['status']}, {record['seconds']:.1f}s, "
                f"mechanical={record['mechanical_pass']}",
                flush=True,
            )
    write_summary(root, records)
    print(f"COMPLETE {root / 'summary.md'}")


if __name__ == "__main__":
    main()
