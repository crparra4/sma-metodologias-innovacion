from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_langgraph_workflow import FakeRuntime
from test_sharing import register

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import Verdict
from ruta_dia_agents.tree_diagnosis import ModelReview, grounded, rule_findings
from ruta_dia_agents.web import create_app


def node(node_id, text, source="", parent=""):
    return {"id": node_id, "text": text, "source": source, "parent": parent}


# Mismo par de árboles con el que se decidió el alcance de la revisión.
FLAWED = {
    "problem": "Implementar los OKR con IA y crear una app para centralizarlos",
    "problem_source": "",
    "causes": [
        node("c1", "Doce iniciativas en un solo Excel", "Observación"),
        node("c2", "Falta de una app que centralice los datos"),
    ],
    "effects": [node("e1", "Los equipos no ven sus metas")],
}
SOUND = {
    "problem": "Los usuarios esperan 48 minutos para un trámite que dura 6",
    "problem_source": "Medición",
    "causes": [
        node("c1", "La demanda se concentra entre las 8 y las 10", "Conteo"),
        node("c2", "Nadie informa los horarios de menor afluencia", "Entrevista", "c1"),
    ],
    "effects": [node("e1", "Uno de cada cinco usuarios se va sin terminar", "Registro")],
}


def codes(findings):
    return {(finding.code, finding.target) for finding in findings}


def test_rules_flag_the_flawed_tree():
    found = codes(rule_findings(FLAWED))
    assert ("sin_fuente", "tree") in found
    assert ("sin_causa_de_fondo", "causes") in found
    assert ("falta_de_solucion", "c2") in found
    assert ("falta_de_solucion", "c1") not in found


def test_rules_stay_quiet_on_a_sound_tree():
    # Ninguna alarma: todas las tarjetas tienen fuente, hay causa de fondo y ninguna
    # causa nombra lo que falta. "Nadie informa..." describe lo que ocurre.
    assert rule_findings(SOUND) == []


@pytest.mark.parametrize("text", [
    "Falta de una app", "Faltan datos del área", "No hay un sistema común",
    "No existe un responsable", "Ausencia de indicadores", "Sin tablero compartido",
])
def test_absence_rule_matches_the_textbook_phrasings(text):
    tree = {**SOUND, "causes": [node("c1", text, "x")]}
    assert ("falta_de_solucion", "c1") in codes(rule_findings(tree))


def test_empty_lanes_duplicates_and_short_cards():
    tree = {**SOUND, "effects": [], "causes": [
        node("c1", "Pocos turnos", "Conteo"),
        node("c2", "pocos   TURNOS", "Conteo", "c1"),
    ]}
    found = codes(rule_findings(tree))
    assert ("carril_vacio", "effects") in found
    assert ("repetida", "c2") in found
    assert ("muy_breve", "c1") in found


def test_problem_review_must_quote_the_problem_literally():
    ok = ModelReview(
        problem_solution_fragment="crear una app", problem_explanation="Es una solución",
    )
    kept, discarded = grounded(ok, FLAWED)
    assert codes(kept) == {("problema_como_solucion", "problem")}
    assert discarded == 0
    # la explicación cortada por el límite de salida no muestra media palabra
    assert kept[0].message == "Es una solución…"

    invented = ModelReview(problem_solution_fragment="migrar a la nube",
                           problem_explanation="Es una solución.")
    assert grounded(invented, FLAWED) == ([], 1)
    silent = ModelReview(problem_solution_fragment="", problem_explanation="")
    assert grounded(silent, SOUND) == ([], 0)


class ReviewingRuntime(FakeRuntime):
    def __init__(self, review=None, error=None):
        super().__init__([Verdict.APPROVED])
        self.review, self.error, self.prompts = review, error, []

    def review_tree(self, description):
        self.prompts.append(description)
        if self.error:
            raise self.error
        return self.review


def client_with(tmp_path, runtime):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    return TestClient(create_app(
        settings, runtime_factory=lambda _: runtime, model_probe=lambda _: True,
    ))


def saved_tree_endpoint(client, tree):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "OKR", "context": {"question": "Reto"},
    })
    endpoint = f"/api/projects/{created.json()['project_id']}/problem-tree"
    assert client.post(f"{endpoint}/diagnosis").status_code == 409  # nada guardado todavía
    saved = client.put(endpoint, json={"version": 0, **tree})
    assert saved.status_code == 200, saved.text
    return f"{endpoint}/diagnosis"


def test_diagnosis_combines_rules_and_model(tmp_path):
    runtime = ReviewingRuntime(review=ModelReview(
        problem_solution_fragment="crear una app", problem_explanation="Describe una solución.",
    ))
    client = client_with(tmp_path, runtime)
    with client:
        body = client.post(saved_tree_endpoint(client, FLAWED)).json()
    assert body["model_status"] == "ok"
    assert body["version"] == 1
    found = {(item["layer"], item["code"], item["target"]) for item in body["findings"]}
    assert ("contenido", "problema_como_solucion", "problem") in found
    assert ("regla", "falta_de_solucion", "c2") in found
    # el modelo recibe la ficha y el problema central
    assert "Cómo se usa (paso a paso)" in runtime.prompts[0]
    assert FLAWED["problem"] in runtime.prompts[0]


def test_diagnosis_degrades_to_rules_when_model_fails(tmp_path):
    client = client_with(tmp_path, ReviewingRuntime(error=ConnectionError("sin modelo")))
    with client:
        body = client.post(saved_tree_endpoint(client, FLAWED)).json()
    assert body["model_status"] == "no_disponible"
    assert body["findings"]
    assert all(item["layer"] == "regla" for item in body["findings"])
