import json
from types import SimpleNamespace

from test_langgraph_workflow import FakeRuntime
from test_sharing import register
from test_tree_diagnosis import FLAWED, client_with, node

from hilo.acompanamiento.runtime import five_whys_asks_user_why, locked_tool_selection
from hilo.compartido.contracts import Verdict
from hilo.herramientas.why_analysis import (
    apply_turn,
    as_clause,
    context_text,
    is_unknown,
    review_notice,
)

TREE = {
    **FLAWED,
    "causes": [
        node("c1", "Doce iniciativas en un solo Excel", "Observación"),
        node("c2", "Nadie actualiza los KR", "Entrevista", "c1"),
    ],
}


class RecordingRuntime(FakeRuntime):
    """Respuestas simuladas; guarda el estado que recibe el Orquestador."""

    def __init__(self):
        super().__init__([Verdict.APPROVED] * 20)
        self.states = []

    def orchestrate(self, message, state, route_index):
        self.states.append(state)
        return super().orchestrate(message, state, route_index)


def analysis(**overrides):
    return {"cause_text": "Doce iniciativas en un solo Excel", "problem_text": "Problema",
            "steps": [], "doubts": [], "reviewing": False, "awaiting_plan": False,
            "notice": "", **overrides}


def test_unknown_answers_are_recognized():
    for text in ("No sé", "no lo sé todavía", "No tengo idea", "Desconozco eso", "ni idea"):
        assert is_unknown(text)
    for text in ("Nadie sabe usar el tablero", "No hay responsable", "Sé que falta tiempo"):
        assert not is_unknown(text)


def test_context_asks_about_the_last_answer_not_the_original_cause():
    empty = context_text(analysis())
    assert "«¿Por qué ocurre que doce iniciativas en un solo Excel?»" in empty
    one = context_text(analysis(steps=[{"text": "Nadie lo actualiza", "evidence": ""}]))
    assert "«¿Por qué ocurre que nadie lo actualiza?»" in one
    assert "1) Nadie lo actualiza" in one
    five = context_text(analysis(steps=[{"text": f"r{i}", "evidence": ""} for i in range(5)]))
    assert "propón revisar la cadena" in five
    review = context_text(analysis(reviewing=True, steps=[{"text": "r", "evidence": ""}]))
    assert "¿qué conexión entre dos respuestas te parece más débil y por qué?" in review
    assert "No afirmes que ya es la causa raíz" in review


def test_locked_selection_prefers_the_current_stage():
    route = {"stages": [{"id": 1, "tools": [{"id": "cinco-porques"}]},
                        {"id": 3, "tools": [{"id": "cinco-porques"}, {"id": "x"}]}]}
    assert locked_tool_selection("cinco-porques", route, 3) == "3:cinco-porques"
    assert locked_tool_selection("cinco-porques", route, 7) == "1:cinco-porques"
    assert locked_tool_selection("", route, 1) is None
    assert locked_tool_selection("pestel", route, 1) is None


def project(client):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "OKR", "context": {"question": "Reto"},
    }).json()
    base = f"/api/projects/{created['project_id']}"
    assert client.put(f"{base}/problem-tree", json={"version": 0, **TREE}).status_code == 200
    return created["project_id"], base


def chat(client, project_id, message):
    response = client.post("/api/chat", json={
        "notebook_id": "OKR", "project_id": project_id, "message": message,
    })
    assert response.status_code == 200, response.text


def test_start_rules(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, base = project(client)
        analyses = f"{base}/why-analyses"
        assert client.post(analyses, json={"cause_id": "zz"}).status_code == 404
        # una causa de fondo ya no admite otra debajo
        assert client.post(analyses, json={"cause_id": "c2"}).status_code == 409
        started = client.post(analyses, json={"cause_id": "c1"})
        assert started.status_code == 201, started.text
        assert started.json()["cause_text"] == "Doce iniciativas en un solo Excel"
        # solo un análisis en curso por proyecto
        assert client.post(analyses, json={"cause_id": "c1"}).status_code == 409


def test_chat_records_answers_and_locks_the_tool(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, base = project(client)
        analysis_id = client.post(f"{base}/why-analyses", json={"cause_id": "c1"}).json()["id"]

        def current():
            return next(item for item in client.get(f"{base}/why-analyses").json()
                        if item["id"] == analysis_id)

        chat(client, project_id, "Quiero profundizar con cinco porqués esta causa.")
        assert current()["steps"] == []  # el primer mensaje solo abre el análisis
        assert runtime.states[-1].locked_tool == "cinco-porques"
        assert any("Análisis de 5 porqués en curso" in item
                   for item in runtime.states[-1].shared_context)

        chat(client, project_id, "Porque cada área lleva su propio archivo")
        # el agente pregunta por la última respuesta
        assert "¿Por qué ocurre que cada área lleva su propio archivo?" in json.dumps(
            runtime.states[-1].shared_context, ensure_ascii=False)

        chat(client, project_id, "No sé")
        state = current()
        assert [step["text"] for step in state["steps"]] == [
            "Porque cada área lleva su propio archivo"]
        assert state["doubts"] == ["¿Por qué ocurre «Porque cada área lleva su propio archivo»?"]
        assert state["awaiting_plan"]
        assert "No repitas esa pregunta" in json.dumps(
            runtime.states[-1].shared_context, ensure_ascii=False)

        # lo que sigue al «no sé» es el plan para averiguarlo, no un paso de la cadena
        chat(client, project_id, "Puedo revisar las carpetas compartidas")
        state = current()
        assert len(state["steps"]) == 1 and not state["awaiting_plan"]
        assert state["doubts"][0].endswith("Plan: Puedo revisar las carpetas compartidas")
        assert "quedó por investigar" in json.dumps(
            runtime.states[-1].shared_context, ensure_ascii=False)

        # durante la revisión, lo que se escribe comenta la cadena y no es un paso
        assert client.post(f"{base}/why-analyses/{analysis_id}/review").status_code == 200
        chat(client, project_id, "El segundo salto me parece débil")
        assert len(current()["steps"]) == 1
        # la pregunta de revisión no se repite cuando la persona ya la respondió
        chat(client, project_id, "No sé, todas me parecen bien")
        assert current()["review_turns"] == 2
        assert "terminar y elegir" in json.dumps(
            runtime.states[-1].shared_context, ensure_ascii=False)

        # evidencia editable desde la interfaz
        updated = client.patch(f"{base}/why-analyses/{analysis_id}", json={
            "steps": [{"text": "Porque cada área lleva su propio archivo",
                       "evidence": "Revisión de carpetas"}],
        })
        assert updated.json()["steps"][0]["evidence"] == "Revisión de carpetas"


def test_close_and_incorporate_into_the_tree(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, base = project(client)
        analysis_id = client.post(f"{base}/why-analyses", json={"cause_id": "c1"}).json()["id"]
        done = f"{base}/why-analyses/{analysis_id}"
        # no se cierra sin respuestas
        assert client.post(f"{done}/close", json={"candidate": "x"}).status_code == 409
        chat(client, project_id, "Quiero profundizar con cinco porqués.")
        chat(client, project_id, "Nadie definió un formato común")
        client.patch(done, json={"steps": [
            {"text": "Nadie definió un formato común", "evidence": "Entrevista 3"}]})
        # no se incorpora antes de cerrar
        assert client.post(f"{done}/incorporate").status_code == 409
        closed = client.post(f"{done}/close", json={"candidate": "Nadie definió un formato común"})
        assert closed.json()["status"] == "cerrado"

        added = client.post(f"{done}/incorporate")
        assert added.status_code == 200, added.text
        tree = client.get(f"{base}/problem-tree").json()
        assert tree["version"] == 2
        new = next(item for item in tree["causes"] if item["id"] == added.json()["node_id"])
        assert new["parent"] == "c1"
        assert new["source"] == "Entrevista 3 · Análisis de 5 porqués"
        assert client.post(f"{done}/incorporate").status_code == 409  # una sola vez

        # cerrado: deja de fijar la herramienta y de llegar al contexto
        chat(client, project_id, "Gracias")
        assert runtime.states[-1].locked_tool == ""
        assert not any("Análisis de 5 porqués en curso" in item
                       for item in runtime.states[-1].shared_context)


def test_asking_the_user_why_is_not_role_reversal():
    def asks(message, tool="cinco-porques"):
        return five_whys_asks_user_why(SimpleNamespace(message=message),
                                       SimpleNamespace(active_tool=tool))
    assert asks("Aunque no esté confirmado, ¿por qué crees que ocurre?")
    assert asks("¿Por qué cada área arma su propio seguimiento?")
    # pedirle a la persona que pregunte sí invierte los roles
    assert not asks("Hazme la pregunta de por qué ocurre")
    assert not asks("¿Qué quieres que te pregunte?")
    # fuera de cinco porqués no aplica la excepción
    assert not asks("¿Por qué ocurre?", tool="pestel")


def test_answers_become_clauses_for_the_next_question():
    clause = as_clause("Porque cada área lleva su propio archivo.")
    assert clause == "cada área lleva su propio archivo"
    assert as_clause("Creo que nunca se definió un formato") == "nunca se definió un formato"
    assert as_clause("Pues creo que falta tiempo") == "falta tiempo"
    assert as_clause("KR sin responsable") == "KR sin responsable"  # siglas intactas


def test_doubts_reach_the_agent_as_statements():
    text = context_text(analysis(
        steps=[{"text": "Cada área lleva su archivo", "evidence": ""}],
        doubts=["¿Por qué ocurre «Cada área lleva su archivo»? Plan: preguntar a líderes"],
    ))
    assert "el motivo de «Cada área lleva su archivo» (plan: preguntar a líderes)" in text
    assert "¿Por qué ocurre «Cada área" not in text


def step(text):
    return {"text": text, "evidence": ""}


def test_answers_that_do_not_explain_stay_out_of_the_chain():
    # cada caso salió de una prueba con el modelo real (septiembre de 2026)
    for message, kind in [
        ("por muchas cosas", "vaga"),
        ("Porque sí", "vaga"),
        ("Porque no hemos comprado Power BI", "solucion"),
        ("Falta una herramienta que centralice los datos", "solucion"),
        ("¿Cuánto cuesta una licencia de Power BI?", "pregunta"),
    ]:
        turn = apply_turn(analysis(), message)
        assert turn["steps"] == [] and turn["notice"].startswith(kind + "|"), message
    # causas legítimas que se parecen a las anteriores sí entran
    for message in ("No hay tiempo para consolidar", "Falta un responsable por KR",
                    "¿Porque nadie lo pidió?", "Varias áreas usan su propio formato"):
        assert apply_turn(analysis(), message)["steps"] == [step(message)], message


def test_insisting_records_the_answer():
    first = apply_turn(analysis(), "Porque no hemos comprado Power BI")
    second = apply_turn(analysis(notice=first["notice"]), "Porque no hemos comprado Power BI")
    assert second["steps"] == [step("Porque no hemos comprado Power BI")]
    assert second["notice"] == ""


def test_not_knowing_the_plan_or_a_hypothesis():
    base = analysis(steps=[step("Cada área lleva su archivo")])
    first = apply_turn(base, "no sé, dímelo tú")
    assert first["awaiting_plan"] and len(first["doubts"]) == 1
    # «tampoco sé» no es un plan
    second = apply_turn({**base, **first}, "tampoco sé")
    assert second["doubts"][0].endswith("Plan: sin definir") and not second["awaiting_plan"]
    assert "¿por qué crees que cada área lleva su archivo?" in context_text({**base, **second})
    # sin hipótesis tampoco: no se insiste
    third = apply_turn({**base, **second}, "no sé")
    assert third["notice"] == "sin_hipotesis|" and third["doubts"] == second["doubts"]
    text = context_text({**base, **third})
    assert "No insistas" in text and "¿por qué crees" not in text


def test_context_explains_what_was_left_out():
    vague = context_text(analysis(notice="vaga|por muchas cosas"))
    assert "¿qué es lo que más pesa?" in vague and "¿Por qué ocurre que" not in vague
    tool = context_text(analysis(notice="solucion|Porque no hemos comprado Power BI"))
    assert "¿Qué dificultad concreta hay hoy que esa herramienta resolvería?" in tool
    asked = context_text(analysis(steps=[step("Nadie lo actualiza")],
                                  notice="pregunta|¿Cuánto cuesta?"))
    assert "No la respondas con datos" in asked
    assert "«¿Por qué ocurre que nadie lo actualiza?»" in asked


def test_review_does_not_repeat_its_question():
    steps = [step("r1"), step("r2")]
    opened = context_text(analysis(reviewing=True, review_turns=1, steps=steps))
    assert "¿qué conexión entre dos respuestas te parece más débil" in opened
    commented = context_text(analysis(reviewing=True, review_turns=2, steps=steps,
                                      notice=review_notice("La 1 y la 2 no encajan")))
    assert "¿Qué otra razón" in commented and "más débil y por qué" not in commented
    none = context_text(analysis(reviewing=True, review_turns=2, steps=steps,
                                 notice=review_notice("no sé, todas me parecen bien")))
    assert "terminar y elegir" in none and "más débil y por qué" not in none


def test_a_sensitive_message_is_never_recorded_as_a_step(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, base = project(client)
        analysis_id = client.post(f"{base}/why-analyses", json={"cause_id": "c1"}).json()["id"]

        def steps():
            return next(item for item in client.get(f"{base}/why-analyses").json()
                        if item["id"] == analysis_id)["steps"]

        chat(client, project_id, "Quiero profundizar con cinco porqués esta causa.")
        chat(client, project_id, "Nadie definió un formato común")
        assert len(steps()) == 1
        calls = len(runtime.states)
        chat(client, project_id, "Ya no aguanto, a veces pienso en quitarme la vida.")
        assert len(steps()) == 1  # no entra a la cadena de causas
        assert len(runtime.states) == calls  # ni llega al Orquestador
