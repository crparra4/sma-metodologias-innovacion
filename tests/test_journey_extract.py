"""Notas de entrevista → post-its propuestos: solo pasa lo que está literal en las notas."""

import pytest
from pydantic import ValidationError
from test_journey import JOURNEY
from test_sharing import register
from test_tree_diagnosis import client_with
from test_why_analysis import RecordingRuntime

from hilo.herramientas.journey_extract import (
    MAX_PROPOSALS,
    NotesRequest,
    extraction_model,
    extraction_prompt,
    grounded_quotes,
)

NOTES = (
    "Yo llamo siempre por la mañana. Me toca esperar como veinte minutos en la línea y a veces "
    "se cae la llamada. La señorita que contesta es muy amable.   Ojalá  me devolvieran la "
    "llamada en vez de dejarme esperando."
)


ITEM = {"quote": "se cae la llamada", "moment": "x", "stage": "1", "lane": "dolores"}


def output(*items):
    return extraction_model(len(JOURNEY["stages"]))(
        items=[{"quote": quote, "moment": "x", "stage": stage, "lane": lane}
               for quote, stage, lane in items],
    )


# ---------- la comprobación en código ----------

def test_a_literal_quote_is_proposed_with_its_stage_and_lane():
    proposals, discarded = grounded_quotes(
        output(("Me toca esperar como veinte minutos en la línea", "1", "dolores")), NOTES, JOURNEY,
    )
    assert discarded == 0
    assert proposals == [{
        "quote": "Me toca esperar como veinte minutos en la línea",
        "stage_id": "s1", "lane": "dolores", "lane_name": "Dolores",
    }]


def test_the_quote_is_returned_as_written_in_the_notes():
    # el modelo cambia mayúsculas, espacios y añade comillas: se devuelve el texto original
    proposals, _ = grounded_quotes(
        output(("«ojalá me devolvieran la llamada en vez de dejarme esperando.»", "1",
                "oportunidades")), NOTES, JOURNEY,
    )
    assert proposals[0]["quote"] == "Ojalá me devolvieran la llamada en vez de dejarme esperando"


@pytest.mark.parametrize("quote", [
    "Espera veinte minutos en la línea",  # resumida: cambió palabras
    "Le cobran la llamada",  # inventada
    "muy amable",  # menos de tres palabras
])
def test_anything_that_is_not_literal_is_discarded(quote):
    proposals, discarded = grounded_quotes(output((quote, "1", "dolores")), NOTES, JOURNEY)
    assert proposals == [] and discarded == 1


def test_repeats_and_notes_already_on_the_map_are_skipped_without_counting_as_errors():
    notes = NOTES + " Espera veinte minutos en la línea."
    proposals, discarded = grounded_quotes(
        output(
            ("se cae la llamada", "1", "dolores"),
            ("Se cae la llamada", "2", "dolores"),  # la misma frase otra vez
            ("Espera veinte minutos en la línea", "1", "dolores"),  # ya es un post-it (d1)
        ), notes, JOURNEY,
    )
    assert [item["quote"] for item in proposals] == ["se cae la llamada"]
    assert discarded == 0


def test_the_schema_only_allows_existing_stages_and_lanes():
    model = extraction_model(3)
    with pytest.raises(ValidationError):
        model(items=[{**ITEM, "stage": "4"}])
    with pytest.raises(ValidationError):
        model(items=[{**ITEM, "lane": "emociones"}])
    with pytest.raises(ValidationError):
        model(items=[ITEM] * (MAX_PROPOSALS + 1))


def test_the_prompt_carries_the_stages_and_asks_for_exact_copies():
    prompt = extraction_prompt(NOTES, JOURNEY)
    assert "1. Llamar (ya se anotó: Marca al número de la EPS; Espera veinte" in prompt
    assert "\n3. Asistir\n" in prompt
    assert "EXACTAMENTE" in prompt and NOTES in prompt


def test_notes_have_a_size_limit():
    with pytest.raises(ValidationError):
        NotesRequest(text="muy corto")
    with pytest.raises(ValidationError):
        NotesRequest(text="palabra " * 400)


# ---------- la API ----------

class NotesRuntime(RecordingRuntime):
    """Simula al modelo: una cita literal, una inventada y una resumida."""

    def extract_journey(self, description, output_model):
        self.prompt = description
        return output_model(items=[
            {"quote": "a veces se cae la llamada", "moment": "llama", "stage": "1",
             "lane": "dolores"},
            {"quote": "Le cobran la llamada", "moment": "llama", "stage": "1", "lane": "dolores"},
            {"quote": "La señorita que contesta es muy amable", "moment": "agenda", "stage": "2",
             "lane": "contacto"},
        ])


def journey_project(client, journey=JOURNEY):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "Citas", "context": {"question": "Reto"},
    }).json()
    base = f"/api/projects/{created['project_id']}/journey"
    if journey:
        assert client.put(base, json={"version": 0, **journey}).status_code == 200
    return base


def test_extract_returns_grounded_proposals_and_saves_nothing(tmp_path):
    runtime = NotesRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        base = journey_project(client)
        response = client.post(f"{base}/extract", json={"text": NOTES})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["model_status"] == "ok" and result["discarded"] == 1
        found = [(item["quote"], item["stage_id"], item["lane"]) for item in result["proposals"]]
        assert found == [
            ("a veces se cae la llamada", "s1", "dolores"),
            ("La señorita que contesta es muy amable", "s2", "contacto"),
        ]
        assert "Me toca esperar" in runtime.prompt
        assert client.get(base).json()["version"] == 1  # el recorrido no cambió


def test_extract_needs_stages_first(tmp_path):
    client = client_with(tmp_path, NotesRuntime())
    with client:
        base = journey_project(client, journey=None)
        response = client.post(f"{base}/extract", json={"text": NOTES})
        assert response.status_code == 409 and "etapas" in response.json()["detail"]


def test_extract_degrades_when_the_model_cannot_read_notes(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())  # sin `extract_journey`
    with client:
        base = journey_project(client)
        result = client.post(f"{base}/extract", json={"text": NOTES}).json()
        assert result == {**result, "proposals": [], "model_status": "no_disponible"}
