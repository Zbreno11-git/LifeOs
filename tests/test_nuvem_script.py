"""`scripts/nuvem.py` (Sessão 10, D58): sem flag só lê, e nenhum `gcloud` sai sem o projeto do
Viking.

O VPS roda com o login do dono, que alcança todos os projetos dele, e o projeto padrão da
configuração é **outro** projeto dele (D47 revista). A parede é esta: todo comando nasce em
`_gcloud`, que põe `--project=<o do Viking>`, e `_rodar` recusa o que chegar sem ele. Nenhum
teste chama o `gcloud` de verdade: `_rodar` é trocado por um gravador.
"""

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "nuvem.py"


@pytest.fixture(scope="module")
def nuvem():
    spec = importlib.util.spec_from_file_location("nuvem_script", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["nuvem_script"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def ctx(nuvem):
    return nuvem.Contexto(
        projeto="viking-teste",
        regiao="southamerica-east1",
        faturamento="000000-000000-000000",
        orcamento="105BRL",
        dono="dono@example.com",
    )


_LEITURAS = {"describe", "list", "get-iam-policy"}


def _verbo(comando: list[str]) -> str:
    return next(a for a in comando[1:] if a in _LEITURAS | _ESCRITAS)


_ESCRITAS = {
    "create",
    "link",
    "enable",
    "set-cleanup-policies",
    "add-iam-policy-binding",
    "deploy",
}


def test_so_gcloud_monta_e_so_rodar_executa(nuvem):
    """Lendo o código: o literal "gcloud" só em `_gcloud`, `_rodar` e o `config get account` de
    `_contexto` (que lê a conta ativa, não um projeto); `subprocess` só nesses dois últimos."""
    arvore = ast.parse(SCRIPT.read_text())
    permitidas = {"_gcloud", "_rodar", "_contexto"}
    achados = []
    for funcao in ast.walk(arvore):
        if not isinstance(funcao, ast.FunctionDef):
            continue
        for no in ast.walk(funcao):
            literal = isinstance(no, ast.Constant) and no.value == "gcloud"
            chamada = (
                isinstance(no, ast.Attribute)
                and isinstance(no.value, ast.Name)
                and no.value.id == "subprocess"
            )
            if (literal or chamada) and funcao.name not in permitidas:
                achados.append((funcao.name, no.lineno))
    assert achados == []


def test_rodar_recusa_comando_sem_o_projeto(nuvem):
    with pytest.raises(nuvem.ErroDoGcloud):
        nuvem._rodar(["gcloud", "projects", "list"])
    with pytest.raises(nuvem.ErroDoGcloud):
        nuvem._rodar(["sh", "-c", "gcloud projects list --project=x"])


def test_todo_comando_de_todo_passo_leva_o_projeto_do_viking(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_ler", lambda _c: None)  # tudo "a criar"
    comandos = [c for passo in nuvem.PASSOS for c in passo.comandos(ctx)]
    assert len(comandos) >= 10
    for comando in comandos:
        assert comando[0] == "gcloud"
        assert "--project=viking-teste" in comando, comando
        assert not any(
            a.startswith("--project=") and a != "--project=viking-teste" for a in comando
        )


class _Gravador:
    """Faz as vezes do `gcloud`: devolve o estado de um projeto que ainda não existe e grava cada
    comando que chegou."""

    def __init__(self, respostas=None):
        self.comandos: list[list[str]] = []
        self.respostas = respostas or {}

    def __call__(self, comando):
        self.comandos.append(comando)
        if _verbo(comando) in _ESCRITAS:
            return subprocess.CompletedProcess(comando, 0, "", "")
        chave = " ".join(a for a in comando[1:] if not a.startswith("--"))
        for inicio, saida in self.respostas.items():
            if chave.startswith(inicio):
                return subprocess.CompletedProcess(comando, 0, json.dumps(saida), "")
        return subprocess.CompletedProcess(comando, 1, "", "ERROR: NOT_FOUND: was not found")


def test_sem_flag_so_le(nuvem, ctx, monkeypatch, capsys):
    gravador = _Gravador({"projects describe": {"lifecycleState": "ACTIVE"}})
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    monkeypatch.setattr(nuvem, "_contexto", lambda: ctx)

    assert nuvem.main([]) == 0

    assert gravador.comandos  # mediu de verdade
    assert {_verbo(c) for c in gravador.comandos} <= _LEITURAS
    saida = capsys.readouterr().out
    assert "Nada foi mudado" in saida
    assert "→ gcloud firestore databases create" in saida  # mostra o que criaria
    assert "irreversível" in saida
    assert "--project=" not in saida  # a flag que todo comando leva não polui a leitura
    assert "000000-000000-000000" not in saida and "…000000" in saida  # a conta, só o fim


def test_sem_projeto_a_listagem_nao_le_nada_alem_do_projeto(nuvem, ctx, monkeypatch, capsys):
    """Achado na 1ª execução de verdade (2026-09-29): listar o registro e as contas lia um projeto
    que não existe, e o erro derrubava a listagem."""
    gravador = _Gravador()  # nada existe
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    monkeypatch.setattr(nuvem, "_contexto", lambda: ctx)
    assert nuvem.main([]) == 0
    assert [c[1:3] for c in gravador.comandos] == [["projects", "describe"]]
    assert "→ gcloud iam service-accounts create viking-cli" in capsys.readouterr().out


def test_executar_roda_so_o_passo_pedido_e_mede_de_novo(nuvem, ctx, monkeypatch):
    gravador = _Gravador({"projects describe": {"lifecycleState": "ACTIVE"}})
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    monkeypatch.setattr(nuvem, "_contexto", lambda: ctx)

    codigo = nuvem.main(["--executar", "apis"])

    escritas = [c for c in gravador.comandos if _verbo(c) in _ESCRITAS]
    assert [c[1:3] for c in escritas] == [["services", "enable"]]
    assert codigo == 2  # o gravador não liga nada: a medida depois diz que ainda falta


def test_sem_projeto_os_passos_seguintes_nao_sao_medidos(nuvem, ctx, monkeypatch):
    gravador = _Gravador()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    medidos = nuvem.medir(ctx)
    assert all(e.detalhe.startswith("depende de ") for _p, e in medidos[1:])
    assert len(gravador.comandos) == 1


def test_passo_com_dependencia_pendente_nao_e_medido(nuvem, ctx, monkeypatch):
    """Achado na criação de verdade (2026-09-29): com o projeto criado e as APIs desligadas, medir
    o Firestore respondia SERVICE_DISABLED e derrubava o script antes de executar o passo seguinte."""
    gravador = _Gravador({"projects describe": {"lifecycleState": "ACTIVE"}})
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    estados = {p.nome: e for p, e in nuvem.medir(ctx)}
    assert estados["projeto"].pronto
    assert estados["firestore"].detalhe == "depende de apis"
    assert estados["indices"].detalhe == "depende de firestore"
    assert not any("firestore" in c for c in gravador.comandos)


def test_erro_que_nao_e_ausencia_sobe(nuvem, ctx, monkeypatch):
    def negado(comando):
        return subprocess.CompletedProcess(comando, 1, "", "ERROR: PERMISSION_DENIED: nope")

    monkeypatch.setattr(nuvem, "_rodar", negado)
    with pytest.raises(nuvem.ErroDoGcloud, match="PERMISSION_DENIED"):
        nuvem._m_apis(ctx)


def test_firestore_noutra_regiao_nao_esta_pronto(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(
        nuvem,
        "_ler",
        lambda _c: {
            "locationId": "us-west1",
            "type": "FIRESTORE_NATIVE",
            "deleteProtectionState": "DELETE_PROTECTION_ENABLED",
        },
    )
    assert not nuvem._m_firestore(ctx).pronto


def test_orcamento_com_outro_valor_nao_esta_pronto(nuvem, ctx, monkeypatch):
    orcamento = {
        "displayName": "viking",
        "amount": {"specifiedAmount": {"units": "500", "currencyCode": "BRL"}},
        "thresholdRules": [{"thresholdPercent": p} for p in (0.5, 0.9, 1.0)],
    }
    monkeypatch.setattr(nuvem, "_ler", lambda _c: [orcamento])
    assert not nuvem._m_orcamento(ctx).pronto
    orcamento["amount"]["specifiedAmount"]["units"] = "105"
    assert nuvem._m_orcamento(ctx).pronto


def test_indices_vem_do_store(nuvem, ctx, monkeypatch):
    """Uma fonte só: o script cria exatamente os índices que o store declara para as consultas."""
    from lifeos.reminders import store_firestore

    monkeypatch.setattr(nuvem, "_ler", lambda _c: [])
    (comando,) = nuvem._c_indices(ctx)
    campos = [a.split("field-path=")[1] for a in comando if "field-path=" in a]
    ((_colecao, esperados),) = store_firestore.INDICES
    assert campos == [f"{c},order={o.lower()}" for c, o in esperados]


def test_ids_das_contas_de_servico_cabem_na_regra_do_google(nuvem):
    """Achado na criação de verdade (2026-09-29): "motor" foi recusado; o ID tem de 6 a 30
    caracteres, minúsculas, dígitos e hífen, começando por letra."""
    import re

    for nome in (nuvem.MOTOR, nuvem.CLI):
        assert re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", nome), nome
