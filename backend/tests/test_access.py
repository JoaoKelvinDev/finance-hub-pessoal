import uuid

import pytest

from tests.conftest import make_token

PRIVATE_ROUTES = ["/api/v1/me", "/api/v1/dashboard", "/api/v1/accounts", "/api/v1/transactions", "/api/v1/people"]


@pytest.mark.parametrize("path", PRIVATE_ROUTES)
def test_sem_sessao_retorna_401(anon_client, path):
    r = anon_client.get(path)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "token",
    [
        "lixo",
        make_token(exp_delta=-10),
        make_token(aud="anon"),
        make_token(secret="outro-segredo-qualquer-com-32-caracteres!"),
    ],
)
def test_token_invalido_retorna_401(anon_client, token):
    r = anon_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_identidade_diferente_do_proprietario_retorna_403(anon_client):
    token = make_token(sub=str(uuid.uuid4()))
    r = anon_client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_id_conhecido_sem_sessao_nao_vaza(client, anon_client):
    acc = client.post(
        "/api/v1/accounts", json={"name": "Banco", "type": "CHECKING", "opening_date": "2026-01-01"}
    ).json()
    assert anon_client.get(f"/api/v1/accounts/{acc['id']}/ledger").status_code == 401


def test_proprietario_acessa(client):
    assert client.get("/api/v1/me").json() == {"owner": True}


def test_nao_existe_cadastro_de_usuarios():
    from app.main import app

    paths = " ".join(app.openapi()["paths"]).lower()
    assert "/api/v1/accounts" in paths
    for forbidden in ("signup", "register", "users", "members", "invite", "roles", "tenant"):
        assert forbidden not in paths
