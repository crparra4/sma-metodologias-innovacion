from test_sharing import (
    accept_first_invitation,
    login,
    logout,
    register,
    sharing_client,
)


def test_problem_tree_shared_access_and_conflict(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        register(client, "ana", "Ana")
        created = client.post("/api/notebooks", json={
            "notebook_id": "Movilidad", "context": {"question": "Esperas largas"},
        })
        project_id = created.json()["project_id"]
        endpoint = f"/api/projects/{project_id}/problem-tree"
        assert client.get(endpoint).json()["version"] == 0

        original = {
            "version": 0, "problem": "Los estudiantes esperan demasiado",
            "problem_source": "Entrevista 1",
            "causes": [{"id": "c1", "text": "Pocos turnos disponibles", "source": ""}],
            "effects": [{"id": "e1", "text": "Llegan tarde", "source": "Observación 2"}],
        }
        saved = client.put(endpoint, json=original)
        assert saved.status_code == 200, saved.text
        assert saved.json()["version"] == 1

        logout(client)
        register(client, "luis", "Luis")
        logout(client)
        register(client, "maria", "María")
        logout(client)
        login(client, "ana")
        for username, role in (("luis", "viewer"), ("maria", "editor")):
            response = client.post(f"/api/projects/{project_id}/invitations", json={
                "username": username, "role": role,
            })
            assert response.status_code == 201, response.text
        logout(client)

        login(client, "luis")
        accept_first_invitation(client)
        assert client.get(endpoint).json()["problem"] == original["problem"]
        assert client.put(endpoint, json={**original, "version": 1}).status_code == 403
        logout(client)

        login(client, "maria")
        accept_first_invitation(client)
        updated = client.put(endpoint, json={**original, "version": 1,
                                             "problem": "La espera supera una hora"})
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        state = client.get(f"/api/notebooks/{project_id}").json()["state"]
        assert any("Árbol de problemas" in item for item in state["shared_context"])
        logout(client)

        login(client, "ana")
        assert client.put(endpoint, json={**original, "version": 1}).status_code == 409
        assert client.get(endpoint).json()["problem"] == "La espera supera una hora"
        invalid = {**original, "version": 2,
                   "causes": [{"id": "c1", "text": "", "source": ""}]}
        assert client.put(endpoint, json=invalid).status_code == 422
