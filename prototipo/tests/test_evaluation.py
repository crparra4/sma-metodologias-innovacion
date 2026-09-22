from dataclasses import replace
from unittest.mock import patch

import httpx

from ruta_dia_agents.config import Settings
from ruta_dia_agents.evaluation import WireRecorder, structural_checks
from ruta_dia_agents.runtime import build_llm


def test_local_model_cannot_fall_back_to_default_cloud_provider():
    settings = replace(
        Settings.from_env(),
        model="local-qwen",
        base_url="http://127.0.0.1:18083/v1",
        api_key="test-key",
        temperature=0.7,
        max_tokens=384,
        seed=42,
    )
    with patch("ruta_dia_agents.runtime.LLM") as factory:
        build_llm(settings)
    options = factory.call_args.kwargs
    assert options["custom_openai"] is True
    assert options["base_url"] == settings.base_url
    assert options["model"] == "local-qwen"
    assert options["max_retries"] == 0
    assert options["seed"] == 42


def test_cloud_default_is_preserved_without_local_endpoint():
    settings = replace(Settings.from_env(), base_url=None, max_tokens=None, seed=None, top_p=None)
    with patch("ruta_dia_agents.runtime.LLM") as factory:
        build_llm(settings)
    assert factory.call_args.kwargs == {
        "model": settings.model,
        "temperature": settings.temperature,
    }


def test_wrong_verdict_and_wrong_source_are_counted_as_failures():
    case = {"kind": "verify", "expected": {"verdict": "rejected"}}
    assert structural_checks(case, {"verdict": "approved", "source_tool_id": "pestel"}) == {
        "expected_verdict": False,
        "correct_source": False,
    }


def test_degradation_does_not_count_as_success_for_a_normal_turn():
    case = {
        "kind": "turn",
        "expected": {
            "stage": 1,
            "active_tool": "cinco-porques",
            "degraded": False,
        },
    }
    result = {"handoff": {"stage": 1, "active_tool": "cinco-porques"}, "degraded": True}
    assert structural_checks(case, result)["expected_degradation"] is False


def test_wire_recorder_keeps_response_and_omits_authorization(tmp_path):
    path = tmp_path / "http.jsonl"
    recorder = WireRecorder(path)
    request = httpx.Request(
        "POST",
        "http://localhost/v1/chat/completions",
        headers={"Authorization": "Bearer secret-token"},
        json={"messages": [{"role": "user", "content": "Hola"}]},
    )
    recorder.on_outbound(request)
    response = httpx.Response(200, json={"choices": [], "usage": {"completion_tokens": 3}})
    assert recorder.on_inbound(response) is response
    text = path.read_text(encoding="utf-8")
    assert "secret-token" not in text
    assert "completion_tokens" in text
