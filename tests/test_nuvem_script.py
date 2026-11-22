"""`scripts/nuvem.py` (Sessão 10, D58): sem flag só lê, e nenhum `gcloud` sai sem o projeto do
Viking.

O VPS roda com o login do dono, que alcança todos os projetos dele, e o projeto padrão da
configuração é **outro** projeto dele (D47 revista). A parede é esta: todo comando nasce em
`_gcloud`, que põe `--project=<o do Viking>`, e `_rodar` recusa o que chegar sem ele. Nenhum
teste chama o `gcloud` de verdade: `_rodar` é trocado por um gravador.
"""

import ast
import dataclasses
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
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
    "remove-iam-policy-binding",
    "deploy",
    "upload",
    "disable",
}


def test_so_gcloud_monta_e_so_rodar_executa(nuvem):
    """Lendo o código: o literal "gcloud" só em `_gcloud`, `_rodar` e o `config get account` de
    `_contexto` (que lê a conta ativa, não um projeto); `subprocess` só nesses dois últimos."""
    arvore = ast.parse(SCRIPT.read_text())
    permitidas = {"_gcloud", "_rodar", "_contexto", "_local"}
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
    """Uma fonte só: o script cria exatamente os índices que os stores declaram para as consultas
    (os lembretes, desde a 10b o registro de ações, desde a 13 o vetorial da memória, e desde a
    14 o dos trechos, com o tema)."""
    from lifeos import registro_firestore
    from lifeos.documentos import store as documentos_store
    from lifeos.memoria import store as memoria_store
    from lifeos.reminders import store_firestore

    assert nuvem.INDICES == (
        store_firestore.INDICES
        + registro_firestore.INDICES
        + memoria_store.INDICES
        + documentos_store.INDICES
    )
    monkeypatch.setattr(nuvem, "_ler", lambda _c: [])
    comandos = nuvem._c_indices(ctx)
    assert len(comandos) == len(nuvem.INDICES) == 4
    for comando, (colecao, esperados) in zip(comandos[:2], nuvem.INDICES[:2], strict=True):
        assert f"--collection-group={colecao}" in comando
        campos = [a.split("field-path=")[1] for a in comando if "field-path=" in a]
        assert campos == [f"{c},order={o.lower()}" for c, o in esperados]
    vetorial = comandos[2]
    assert "--collection-group=memoria" in vetorial
    assert [a for a in vetorial if a.startswith("--field-config=")] == [
        "--field-config=field-path=ativo,order=ascending",
        "--field-config=field-path=vetor,vector-config={dimension=768,flat}",
    ]
    dos_trechos = comandos[3]
    assert "--collection-group=trechos" in dos_trechos
    assert [a for a in dos_trechos if a.startswith("--field-config=")] == [
        "--field-config=field-path=tema_lido,order=ascending",
        "--field-config=field-path=ativo,order=ascending",
        "--field-config=field-path=vetor,vector-config={dimension=768,flat}",
    ]


def test_o_indice_vetorial_listado_conta_como_existente(nuvem, ctx, monkeypatch):
    """A listagem do `gcloud` traz o campo vetorial com `vectorConfig`, sem `order` (a forma da
    API do Firestore): lido como "VECTOR:N", ele casa com o declarado e não se cria de novo."""
    from lifeos.memoria import store as memoria_store

    ((colecao, _campos),) = memoria_store.INDICES
    listado = {
        "name": f"projects/p/databases/(default)/collectionGroups/{colecao}/indexes/9",
        "state": "READY",
        "fields": [
            {"fieldPath": "ativo", "order": "ASCENDING"},
            {"fieldPath": "vetor", "vectorConfig": {"dimension": 768, "flat": {}}},
            {"fieldPath": "__name__", "order": "ASCENDING"},
        ],
    }
    monkeypatch.setattr(nuvem, "_ler", lambda _c: [listado])
    pronto = nuvem.dataclasses.replace(ctx, prontos=frozenset({"firestore"}))
    comandos = nuvem._c_indices(pronto)
    assert not any("--collection-group=memoria" in c for c in comandos)
    outra = dict(
        listado,
        fields=[listado["fields"][0], {"fieldPath": "vetor", "vectorConfig": {"dimension": 3072}}],
    )
    monkeypatch.setattr(nuvem, "_ler", lambda _c: [outra])
    assert any("--collection-group=memoria" in c for c in nuvem._c_indices(pronto))


def test_ids_das_contas_de_servico_cabem_na_regra_do_google(nuvem):
    """Achado na criação de verdade (2026-09-29): "motor" foi recusado; o ID tem de 6 a 30
    caracteres, minúsculas, dígitos e hífen, começando por letra."""
    import re

    for nome in (nuvem.MOTOR, nuvem.CLI, nuvem.MAOS, nuvem.AGENDADOR):
        assert re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", nome), nome


# --- o deploy do motor (C6) ---------------------------------------------------------------------

SHA = "a" * 40


class _Mundo:
    """O gcloud, o git, o docker e o gh de mentira, com o estado de um deploy."""

    def __init__(
        self,
        nuvem,
        *,
        limpo=True,
        publicado=True,
        ci="completed success",
        no_ar=None,
        mudou=3,
        vazios=(),
        vazios_no_ar=None,
        financas=False,
        financas_no_ar=False,
        fuso_no_ar="America/Los_Angeles",
    ):
        self.nuvem = nuvem
        self.fuso_no_ar = fuso_no_ar
        # segredos sem versão no Secret Manager; o da Pluggy (11d) só com `financas=True`
        self.vazios = set(vazios) | ({"viking-pluggy"} if not financas else set())
        # os que a revisão no ar não monta (por padrão, os mesmos que estão sem versão)
        self.vazios_no_ar = self.vazios if vazios_no_ar is None else set(vazios_no_ar)
        self.financas_no_ar = financas_no_ar  # o motor no ar tem a URL do serviço de finanças
        self.gcloud: list[list[str]] = []
        self.local: list[tuple[list[str], str | None]] = []
        self.limpo, self.publicado, self.ci, self.no_ar = limpo, publicado, ci, no_ar
        self.mudou = 0 if no_ar == SHA else mudou

    def rodar(self, comando):
        self.gcloud.append(comando)
        corpo = [a for a in comando[1:] if not a.startswith("--")]
        if corpo[:2] == ["projects", "describe"]:
            return subprocess.CompletedProcess(comando, 0, json.dumps({"projectNumber": "42"}), "")
        if corpo[:3] == ["run", "services", "describe"]:
            if self.no_ar is None:
                return subprocess.CompletedProcess(comando, 1, "", "ERROR: NOT_FOUND")
            volumes = [
                {"name": s.nome, "secret": {"secretName": s.nome}}
                for s in self.nuvem.SEGREDOS
                if s.nome not in self.vazios_no_ar
            ]
            env = [{"name": "VIKING_FINANCAS_URL", "value": "x"}] if self.financas_no_ar else []
            env.append({"name": "VIKING_TIMEZONE", "value": self.fuso_no_ar})
            servico = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{"image": f"x:{self.no_ar}", "env": env}],
                            "volumes": volumes,
                        }
                    }
                }
            }
            return subprocess.CompletedProcess(comando, 0, json.dumps(servico), "")
        if corpo[:1] == ["auth"]:
            return subprocess.CompletedProcess(comando, 0, "TOKEN-SECRETO-123\n", "")
        if corpo[:3] == ["secrets", "versions", "list"]:
            versoes = [] if corpo[3] in self.vazios else [{"name": "v1"}]
            return subprocess.CompletedProcess(comando, 0, json.dumps(versoes), "")
        return subprocess.CompletedProcess(comando, 0, "", "")

    def rodar_local(self, comando, *, entrada=None):
        self.local.append((comando, entrada))
        saidas = {
            ("git", "rev-parse"): SHA,
            ("git", "ls-remote"): f"{SHA if self.publicado else 'b' * 40}\trefs/heads/master",
            ("git", "status"): "" if self.limpo else " M arquivo.py",
            ("git", "rev-list"): str(self.mudou),
            ("gh", "run"): self.ci,
        }
        return subprocess.CompletedProcess(comando, 0, saidas.get(tuple(comando[:2]), ""), "")


@pytest.fixture
def mundo(nuvem, monkeypatch):
    def montar(**estado):
        m = _Mundo(nuvem, **estado)
        monkeypatch.setattr(nuvem, "_rodar", m.rodar)
        monkeypatch.setattr(nuvem, "_local", m.rodar_local)
        monkeypatch.setattr(nuvem, "provas", lambda _ctx, _sha, _montados=(), _fin=False: [])
        monkeypatch.setenv("VIKING_NUVEM_FUSO", "America/Los_Angeles")
        return m

    return montar


def _publicou(m) -> bool:
    return any(c[:2] == ["docker", "push"] for c, _ in m.local) or any(
        "deploy" in c for c in m.gcloud
    )


def test_caminhos_da_imagem_saem_do_dockerfile(nuvem):
    assert nuvem.caminhos_da_imagem() == [
        "Dockerfile",
        ".dockerignore",
        "pyproject.toml",
        "uv.lock",
        "src",
    ]


def test_local_recusa_o_gcloud(nuvem):
    with pytest.raises(nuvem.ErroDoGcloud):
        nuvem._local(["gcloud", "run", "deploy", "--project=x"])


def test_deploy_sem_flag_mostra_e_nao_publica(nuvem, ctx, mundo, capsys):
    m = mundo()
    assert nuvem.deploy(ctx, executar=False) == 0
    assert not _publicou(m)
    saida = capsys.readouterr().out
    assert "Nada foi publicado" in saida and "→ gcloud run deploy motor" in saida


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [
        ({"limpo": False}, "árvore suja"),
        ({"publicado": False}, "HEAD fora do GitHub"),
        ({"ci": "completed failure"}, "CI vermelho"),
        ({"ci": "in_progress "}, "CI rodando"),
    ],
)
def test_deploy_recusa_o_que_nao_e_um_commit_verde(nuvem, ctx, mundo, estado, motivo):
    m = mundo(**estado)
    assert nuvem.deploy(ctx, executar=True) == 1, motivo
    assert not _publicou(m), motivo


def test_deploy_publica_e_o_token_nunca_aparece(nuvem, ctx, mundo, capsys):
    m = mundo()
    assert nuvem.deploy(ctx, executar=True) == 0
    assert _publicou(m)
    (login,) = [(c, e) for c, e in m.local if c[:2] == ["docker", "login"]]
    assert login[1] == "TOKEN-SECRETO-123"  # pela entrada padrão, nunca no argv
    assert not any("TOKEN-SECRETO" in " ".join(c) for c, _ in m.local)
    assert any(c[:2] == ["docker", "logout"] for c, _ in m.local)  # não fica no ~/.docker
    saida = capsys.readouterr()
    assert "TOKEN-SECRETO" not in saida.out + saida.err


def test_o_head_ja_no_ar_so_prova(nuvem, ctx, mundo, capsys):
    m = mundo(no_ar=SHA)
    assert nuvem.deploy(ctx, executar=True) == 0
    assert not _publicou(m)
    assert "só as provas" in capsys.readouterr().out


def test_fuso_trocado_no_env_publica_mesmo_sem_commit(nuvem, ctx, mundo, capsys):
    """14b (D69): o dono se mudou e só o `.env` mudou. A imagem no ar é o HEAD, mas o fuso dela é
    o velho: "nada mudou" deixaria Seattle no ar sem ninguém ver."""
    m = mundo(no_ar=SHA, fuso_no_ar="America/Sao_Paulo")
    assert nuvem.deploy(ctx, executar=True) == 0
    assert _publicou(m)
    assert "só as provas" not in capsys.readouterr().out


def test_commit_que_nao_mexe_na_imagem_nao_publica_de_novo(nuvem, ctx, mundo, monkeypatch):
    """Um commit só em `scripts/` ou `tests/` não muda a imagem: a que está no ar já é o código de
    agora, e as provas comparam com ela (não com o HEAD)."""
    m = mundo(no_ar="b" * 40, mudou=0)
    esperados = []
    monkeypatch.setattr(
        nuvem, "provas", lambda _ctx, sha, _m=(), _f=False: esperados.append(sha) or []
    )
    assert nuvem.deploy(ctx, executar=True) == 0
    assert not _publicou(m)
    assert esperados == ["b" * 40]


def test_commit_que_mexe_na_imagem_publica(nuvem, ctx, mundo):
    m = mundo(no_ar="b" * 40, mudou=1)
    assert nuvem.deploy(ctx, executar=True) == 0
    assert _publicou(m)


def test_o_servico_nasce_fechado(nuvem, ctx, mundo):
    mundo()
    implantar, *permitir = nuvem.comandos_do_deploy(ctx, SHA)
    assert "--no-allow-unauthenticated" in implantar and "--min-instances=0" in implantar
    assert "--max-instances=2" in implantar
    assert f"--service-account=viking-motor@{ctx.projeto}.iam.gserviceaccount.com" in implantar
    (variaveis,) = [a for a in implantar if a.startswith("--set-env-vars=")]
    assert "VIKING_TIMEZONE=America/Los_Angeles" in variaveis
    assert "VIKING_NUVEM_URL=https://motor-42.southamerica-east1.run.app" in variaveis
    # o terminal e as mãos (Sessão 11), cada um num comando; o agendador@ só no passo dele
    membros = [a for c in permitir for a in c if a.startswith("--member=")]
    assert membros == [
        f"--member=serviceAccount:viking-{nome}@{ctx.projeto}.iam.gserviceaccount.com"
        for nome in ("cli", "maos")
    ]
    assert all("--role=roles/run.invoker" in c for c in permitir)
    tudo = [a for c in (implantar, *permitir) for a in c]
    assert not any("allUsers" in a or "allAuthenticatedUsers" in a for a in tudo)
    assert not any("agendador" in a for a in tudo)


def test_sem_fuso_nao_publica(nuvem, ctx, mundo, monkeypatch):
    mundo()
    monkeypatch.delenv("VIKING_NUVEM_FUSO")
    with pytest.raises(SystemExit, match="VIKING_NUVEM_FUSO"):
        nuvem.comandos_do_deploy(ctx, SHA)


def test_servico_inexistente_e_ausencia_nao_erro(nuvem, ctx, monkeypatch):
    """O texto real do `gcloud run services describe` (2026-09-30), que derrubou o 1º deploy."""
    real = "ERROR: (gcloud.run.services.describe) Cannot find service [motor]"
    monkeypatch.setattr(nuvem, "_rodar", lambda c: subprocess.CompletedProcess(c, 1, "", real))
    assert nuvem._ler(["gcloud", "run", "services", "describe", "motor", "--project=x"]) is None


# --- os segredos e a TTL (Sessão 10b) -----------------------------------------------------------


def test_deploy_entrega_os_segredos_so_como_volume_e_o_prazo_do_turno(nuvem, ctx, mundo):
    mundo()
    implantar, *_permitir = nuvem.comandos_do_deploy(ctx, SHA)
    (segredos,) = [a for a in implantar if a.startswith("--set-secrets=")]
    pares = segredos.removeprefix("--set-secrets=").split(",")
    assert pares == [f"{s.caminho}={s.nome}:latest" for s in nuvem.SEGREDOS]
    assert all(par.startswith("/") for par in pares)  # caminho de arquivo, nunca NOME=segredo
    assert len({par.rsplit("/", 1)[0] for par in pares}) == len(pares)  # um diretório cada
    assert not any(a.startswith(("--update-secrets", "--set-secrets=GEMINI")) for a in implantar)
    (variaveis,) = [a for a in implantar if a.startswith("--set-env-vars=")]
    for s in nuvem.SEGREDOS:
        assert f"{s.variavel}={s.caminho}" in variaveis
    assert "GEMINI_API_KEY" not in variaveis
    assert "--timeout=300" in implantar


def test_as_variaveis_dos_segredos_sao_as_que_o_config_le(nuvem):
    from lifeos import config

    fonte = Path(config.__file__).read_text()
    for s in nuvem.TODOS_OS_SEGREDOS:
        assert f'os.getenv("{s.variavel}")' in fonte


def test_todo_arquivo_de_segredo_que_o_config_le_tem_um_segredo_no_deploy(nuvem):
    """Nos dois sentidos, derivado do código: um segredo novo no `config` sem volume no deploy
    (ou o contrário) quebraria o motor só no ar (Sessão 10c: o token do Gmail)."""
    import re

    from lifeos import config

    lidas = set(
        re.findall(r'os\.getenv\("(VIKING_\w+_ARQUIVO)"\)', Path(config.__file__).read_text())
    )
    assert len(lidas) >= 3
    assert lidas == {s.variavel for s in nuvem.TODOS_OS_SEGREDOS}


class _Gcloud:
    def __init__(self, versoes=1, politica=None, existe=True, ttl=None):
        self.chamadas: list[tuple[list[str], str | None]] = []
        self.versoes, self.politica, self.existe, self.ttl = versoes, politica, existe, ttl

    def rodar(self, comando, *, entrada=None):
        self.chamadas.append((comando, entrada))
        corpo = [a for a in comando[1:] if not a.startswith("--")]
        if corpo[:3] == ["secrets", "versions", "list"]:
            saida = json.dumps([{"name": f"v{n}"} for n in range(self.versoes)])
        elif corpo[:2] == ["secrets", "describe"]:
            if not self.existe:
                return subprocess.CompletedProcess(comando, 1, "", "NOT_FOUND")
            saida = json.dumps({"name": corpo[2]})
        elif corpo[:2] == ["secrets", "get-iam-policy"]:
            saida = json.dumps(self.politica or {})
        elif corpo[:3] == ["firestore", "fields", "ttls"]:
            saida = json.dumps(self.ttl or [])
        else:
            saida = ""
        return subprocess.CompletedProcess(comando, 0, saida, "")


def test_segredo_sem_flag_so_mede(nuvem, ctx, monkeypatch, capsys):
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    assert nuvem.segredo(ctx, "viking-gemini", executar=False) == 0
    assert not any("add" in c for c, _ in g.chamadas)
    assert "Nada foi enviado" in capsys.readouterr().out


FALSA = "valor falso do teste"  # não tem forma de chave: o scanner não confunde


def test_segredo_sobe_pela_entrada_padrao_e_nunca_aparece(nuvem, ctx, monkeypatch, capsys):
    from lifeos import config

    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    monkeypatch.setattr(config, "GEMINI_API_KEY", FALSA)
    assert nuvem.segredo(ctx, "viking-gemini", executar=True) == 0
    ((comando, entrada),) = [(c, e) for c, e in g.chamadas if "add" in c]
    assert "--data-file=-" in comando and entrada == FALSA
    assert not any(FALSA in a for c, _ in g.chamadas for a in c)
    assert f"--project={ctx.projeto}" in comando
    assert FALSA not in capsys.readouterr().out


def test_token_da_agenda_que_nao_renova_nao_sobe(nuvem, ctx, monkeypatch, tmp_path):
    from lifeos import config

    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    token = tmp_path / "token.json"
    token.write_text(
        json.dumps({"token": "t", "scopes": ["https://www.googleapis.com/auth/calendar"]})
    )
    monkeypatch.setattr(config, "GOOGLE_TOKEN_PATH", token)
    with pytest.raises(SystemExit, match="não renova"):
        nuvem.segredo(ctx, "viking-agenda", executar=True)
    assert not any("add" in c for c, _ in g.chamadas)


def test_segredo_so_esta_pronto_com_a_leitura_do_motor_e_uma_versao(nuvem, ctx, monkeypatch):
    le = {
        "bindings": [
            {
                "role": nuvem.LER_SEGREDO,
                "members": [f"serviceAccount:viking-motor@{ctx.projeto}.iam.gserviceaccount.com"],
            }
        ]
    }
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(versoes=1, politica={}).rodar)
    assert "não lê" in nuvem._m_segredos(ctx).detalhe
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(versoes=0, politica=le).rodar)
    estado = nuvem._m_segredos(ctx)
    assert not estado.pronto and "vazio" in estado.detalhe
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(versoes=1, politica=le).rodar)
    assert nuvem._m_segredos(ctx).pronto


def test_a_leitura_do_segredo_e_dada_em_cada_segredo_nao_no_projeto(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(existe=False).rodar)
    comandos = nuvem._c_segredos(ctx)
    papeis = [c for c in comandos if any(a.startswith("--role=") for a in c)]
    assert len(papeis) == len(nuvem.SEGREDOS)
    assert all(c[1:3] == ["secrets", "add-iam-policy-binding"] for c in papeis)


def _ttl(colecao, campo, estado):
    nome = f"projects/p/databases/(default)/collectionGroups/{colecao}/fields/{campo}"
    return {"name": nome, "ttlConfig": {"state": estado}}


@pytest.mark.parametrize(
    ("estados", "pronto"),
    [
        (("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE"), True),
        (("ACTIVE", "CREATING", "ACTIVE", "ACTIVE", "ACTIVE"), False),
        (("CREATING", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE"), False),
        (("ACTIVE", "ACTIVE", "ACTIVE", None, "ACTIVE"), False),
        (("ACTIVE", "ACTIVE", None, "ACTIVE", "ACTIVE"), False),
        (("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "CREATING"), False),
        (("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", None), False),
    ],
)
def test_ttl_so_esta_pronta_com_todas_ativas(nuvem, ctx, monkeypatch, estados, pronto):
    estados = estados + ("ACTIVE",) * (len(nuvem.TTLS) - len(estados))  # as da 14 ligadas
    ttl = [_ttl(c, f, e) for (c, f), e in zip(nuvem.TTLS, estados, strict=True) if e]
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(ttl=ttl).rodar)
    assert nuvem._m_ttl(ctx).pronto is pronto


def test_ttl_liga_so_a_que_falta(nuvem, ctx, monkeypatch):
    """As dos documentos são novas (14); as outras cinco já estão ligadas e não se pedem de novo."""
    ttl = [
        _ttl("acoes", "expira_em", "ACTIVE"),
        _ttl("confirmacoes", "apagar_em", "ACTIVE"),
        _ttl("tarefas", "apagar_em", "ACTIVE"),
        _ttl("memoria", "apagar_em", "ACTIVE"),
        _ttl("receitas", "apagar_em", "ACTIVE"),
    ]
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(ttl=ttl).rodar)
    pronto = nuvem.dataclasses.replace(ctx, prontos=frozenset({"firestore"}))
    documentos, trechos = nuvem._c_ttl(pronto)
    assert "--collection-group=documentos" in documentos and "apagar_em" in documentos
    assert "--collection-group=trechos" in trechos and "apagar_em" in trechos


def test_os_campos_da_ttl_sao_os_dos_stores(nuvem):
    from lifeos import confirmacao_firestore, registro_firestore
    from lifeos.documentos import store as documentos_store
    from lifeos.maos import fila_firestore
    from lifeos.memoria import receitas as memoria_receitas
    from lifeos.memoria import store as memoria_store

    assert nuvem.TTLS == (
        (registro_firestore.COLECAO, "expira_em"),
        (confirmacao_firestore.COLECAO, "apagar_em"),
        (fila_firestore.COLECAO, "apagar_em"),
        (memoria_store.COLECAO, "apagar_em"),
        (memoria_receitas.COLECAO, "apagar_em"),
        (documentos_store.COLECAO, "apagar_em"),
        (documentos_store.TRECHOS, "apagar_em"),
    )
    assert "expira_em" in registro_firestore._CAMPOS
    assert "apagar_em" in confirmacao_firestore._CAMPOS
    assert "apagar_em" in fila_firestore._CAMPOS
    assert "apagar_em" in memoria_store._CAMPOS
    assert "apagar_em" in memoria_receitas._CAMPOS
    assert "apagar_em" in documentos_store._CAMPOS
    assert "apagar_em" in documentos_store._CAMPOS_DO_TRECHO


# --- o token do Gmail sobe do Mac (Sessão 10c, D60) ----------------------------------------------


def test_deploy_nao_publica_com_um_segredo_vazio_que_nao_e_do_mac(nuvem, ctx, mundo, capsys):
    m = mundo(vazios={"viking-agenda"})
    assert nuvem.deploy(ctx, executar=True) == 1
    assert not _publicou(m)
    assert "sem valor no Secret Manager: viking-agenda" in capsys.readouterr().out


def _implantado(m):
    (implantar,) = [c for c in m.gcloud if c[1:3] == ["run", "deploy"]]
    (segredos,) = [a for a in implantar if a.startswith("--set-secrets=")]
    (variaveis,) = [a for a in implantar if a.startswith("--set-env-vars=")]
    return segredos, variaveis


def test_deploy_sem_o_token_do_gmail_publica_sem_ele(nuvem, ctx, mundo, capsys):
    """Sessão 11 (D61): o Gmail é opcional na nuvem. Sem versão do `viking-gmail`, a revisão nova
    não monta o volume nem põe a variável (o motor fica sem as tools do Gmail)."""
    m = mundo(vazios={"viking-gmail"})
    assert nuvem.deploy(ctx, executar=True) == 0
    segredos, variaveis = _implantado(m)
    assert "viking-gmail" not in segredos and "viking-agenda" in segredos
    assert "VIKING_GMAIL_TOKEN_ARQUIVO" not in variaveis
    assert "VIKING_AGENDA_TOKEN_ARQUIVO" in variaveis
    assert "Fora desta revisão (sem versão; sobe do Mac): viking-gmail" in capsys.readouterr().out


def test_com_o_token_do_gmail_publica_com_ele(nuvem, ctx, mundo):
    m = mundo()
    assert nuvem.deploy(ctx, executar=True) == 0
    segredos, variaveis = _implantado(m)
    assert "/segredos/gmail/token.json=viking-gmail:latest" in segredos
    assert "VIKING_GMAIL_TOKEN_ARQUIVO=/segredos/gmail/token.json" in variaveis


def test_o_token_do_gmail_que_subiu_pede_revisao_mesmo_sem_codigo_novo(nuvem, ctx, mundo):
    """A segunda vida do script: o motor no ar sem o Gmail, o código igual, e o token subiu do Mac.
    "Nada mudou na imagem" não basta: a revisão no ar não monta o segredo que agora tem versão."""
    m = mundo(no_ar=SHA, vazios_no_ar={"viking-gmail"})
    assert nuvem.deploy(ctx, executar=True) == 0
    assert _publicou(m)
    segredos, _variaveis = _implantado(m)
    assert "viking-gmail" in segredos


def test_o_head_no_ar_com_os_mesmos_segredos_nao_publica(nuvem, ctx, mundo):
    m = mundo(no_ar=SHA, vazios={"viking-gmail"})
    assert nuvem.deploy(ctx, executar=True) == 0
    assert not _publicou(m)


def test_o_segredo_do_mac_vazio_nao_reprova_o_passo(nuvem, ctx, monkeypatch):
    politica = {
        "bindings": [
            {"role": nuvem.LER_SEGREDO, "members": [f"serviceAccount:{ctx.conta(nuvem.MOTOR)}"]}
        ]
    }
    monkeypatch.setattr(nuvem, "_rodar", _Gcloud(versoes=0, politica=politica).rodar)
    estado = nuvem._m_segredos(ctx)
    assert not estado.pronto  # a chave e o token da agenda vazios reprovam
    assert "viking-gmail: vazio (sobe do Mac" in estado.detalhe

    feitos = {s.nome for s in nuvem.SEGREDOS if not s.do_mac}

    class _SoOMacVazio(_Gcloud):
        def rodar(self, comando, *, entrada=None):
            corpo = [a for a in comando[1:] if not a.startswith("--")]
            self.versoes = 1 if corpo[3:4] and corpo[3] in feitos else 0
            return super().rodar(comando, entrada=entrada)

    monkeypatch.setattr(nuvem, "_rodar", _SoOMacVazio(politica=politica).rodar)
    assert nuvem._m_segredos(ctx).pronto


def test_o_segredo_roda_no_mac_so_com_o_projeto(nuvem, monkeypatch):
    for nome in ("VIKING_NUVEM_FATURAMENTO", "VIKING_NUVEM_ORCAMENTO"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("VIKING_NUVEM_PROJETO", "viking-teste")
    conta = subprocess.CompletedProcess([], 0, "dono@example.com\n", "")
    monkeypatch.setattr(nuvem.subprocess, "run", lambda *_a, **_k: conta)
    assert nuvem._contexto(so_projeto=True).dono == "dono@example.com"
    with pytest.raises(SystemExit, match="FATURAMENTO"):
        nuvem._contexto()


_SEM_O_EXTRA_NUVEM = """
import importlib.abc, runpy, sys
class Bloqueia(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho, alvo=None):
        if nome == "google.cloud" or nome.startswith(("google.cloud.", "starlette")):
            raise ImportError("sem o extra nuvem: " + nome)
sys.meta_path.insert(0, Bloqueia())
print(sorted(runpy.run_path(sys.argv[1], run_name="nao_main")["FONTES"]))
"""


def test_o_script_abre_no_mac_sem_o_extra_nuvem():
    """O Mac instala só `--extra dev` (o Firestore e o Starlette são do extra `nuvem`), e é de lá
    que o token do Gmail sobe: importar o script não pode exigir o extra."""
    saida = subprocess.run(
        [sys.executable, "-c", _SEM_O_EXTRA_NUVEM, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert saida.returncode == 0, saida.stderr[-500:]
    assert "viking-gmail" in saida.stdout


REFRESH_FALSO = "refresh-falso-do-teste"  # sem forma de token: o scanner não confunde


def _token_do_gmail(tmp_path, monkeypatch, **mudancas):
    from lifeos import config

    info = {
        "refresh_token": REFRESH_FALSO,
        "client_id": "cliente",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
        **mudancas,
    }
    arquivo = tmp_path / "google_token_gmail.json"
    arquivo.write_text(json.dumps(info))
    monkeypatch.setattr(config, "GMAIL_TOKEN_PATH", arquivo)
    return arquivo.read_text()


def test_o_token_do_gmail_sobe_pela_entrada_padrao_e_nunca_aparece(
    nuvem, ctx, monkeypatch, capsys, tmp_path
):
    texto = _token_do_gmail(tmp_path, monkeypatch)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    assert nuvem.segredo(ctx, "viking-gmail", executar=True) == 0
    ((comando, entrada),) = [(c, e) for c, e in g.chamadas if "add" in c]
    assert "viking-gmail" in comando and "--data-file=-" in comando and entrada == texto
    assert all(REFRESH_FALSO not in " ".join(c) for c, _ in g.chamadas)
    assert REFRESH_FALSO not in capsys.readouterr().out


@pytest.mark.parametrize(
    "mudanca",
    [
        {"scopes": ["https://www.googleapis.com/auth/calendar"]},
        {"refresh_token": ""},
    ],
    ids=["sem-o-escopo-do-gmail", "sem-renovacao"],
)
def test_token_do_gmail_torto_nao_sobe_nem_aparece(
    nuvem, ctx, monkeypatch, capsys, tmp_path, mudanca
):
    _token_do_gmail(tmp_path, monkeypatch, **mudanca)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    with pytest.raises(SystemExit, match="nada foi enviado") as erro:
        nuvem.segredo(ctx, "viking-gmail", executar=True)
    assert not any("add" in c for c, _ in g.chamadas)
    assert REFRESH_FALSO not in str(erro.value) + capsys.readouterr().out


def _servico(env, volumes):
    return {"spec": {"template": {"spec": {"containers": [{"env": env}], "volumes": volumes}}}}


def test_a_prova_recusa_segredo_no_ambiente(nuvem):
    volumes = [{"name": s.nome, "secret": {"secretName": s.nome}} for s in nuvem.SEGREDOS]
    certo = [{"name": s.variavel, "value": s.caminho} for s in nuvem.SEGREDOS]
    assert nuvem._segredos_so_como_volume(_servico(certo, volumes))[0]
    vazado = [*certo, {"name": "GEMINI_API_KEY", "valueFrom": {"secretKeyRef": {"name": "x"}}}]
    assert not nuvem._segredos_so_como_volume(_servico(vazado, volumes))[0]
    assert not nuvem._segredos_so_como_volume(_servico(certo, volumes[:1]))[0]
    # um nome esperado, mas com o valor vindo de um segredo (o segredo no ambiente do processo)
    disfarcado = [
        {"name": s.variavel, "valueFrom": {"secretKeyRef": {"name": s.nome}}}
        for s in nuvem.SEGREDOS
    ]
    assert not nuvem._segredos_so_como_volume(_servico(disfarcado, volumes))[0]


def test_a_prova_dos_volumes_compara_com_os_montados(nuvem):
    sem_gmail = tuple(s for s in nuvem.SEGREDOS if s.nome != "viking-gmail")
    volumes = [{"name": s.nome, "secret": {"secretName": s.nome}} for s in sem_gmail]
    certo = [{"name": s.variavel, "value": s.caminho} for s in sem_gmail]
    assert nuvem._segredos_so_como_volume(_servico(certo, volumes), sem_gmail)[0]
    # o que a revisão não devia montar, montado; ou a variável dele sem o volume
    todos = [{"name": s.nome, "secret": {"secretName": s.nome}} for s in nuvem.SEGREDOS]
    assert not nuvem._segredos_so_como_volume(_servico(certo, todos), sem_gmail)[0]
    gmail = next(s for s in nuvem.SEGREDOS if s.nome == "viking-gmail")
    com_variavel = [*certo, {"name": gmail.variavel, "value": gmail.caminho}]
    assert not nuvem._segredos_so_como_volume(_servico(com_variavel, volumes), sem_gmail)[0]


def test_passo_nao_medido_nao_afirma_que_falta(nuvem, ctx, monkeypatch, capsys):
    """Achado na abertura da 10b (2026-09-30): uma API nova deixou o passo `apis` pendente, e a
    listagem mostrava `firestore databases create` como se o banco não existisse."""
    gravador = _Gravador({"projects describe": {"lifecycleState": "ACTIVE"}})
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    monkeypatch.setattr(nuvem, "_contexto", lambda: ctx)
    nuvem.main([])
    saida = capsys.readouterr().out
    assert "?→ gcloud firestore databases create" in saida
    assert "→ gcloud firestore databases create" not in saida.replace("?→", "")
    assert "não medido: os comandos abaixo só valem se o recurso não existir" in saida


def test_indices_cria_so_o_que_nao_existe(nuvem, ctx, monkeypatch):
    """Achado ao criar o índice do registro (2026-09-30): o passo recriava o dos lembretes, que
    existia, levava ALREADY_EXISTS e parava antes do novo. Construindo também conta como existe."""
    from lifeos.reminders import store_firestore

    ((colecao, campos),) = store_firestore.INDICES
    existente = {
        "name": f"projects/p/databases/(default)/collectionGroups/{colecao}/indexes/1",
        "state": "CREATING",
        "fields": [{"fieldPath": c, "order": o} for c, o in campos],
    }
    monkeypatch.setattr(nuvem, "_ler", lambda _c: [existente])
    pronto = nuvem.dataclasses.replace(ctx, prontos=frozenset({"firestore"}))
    comandos = nuvem._c_indices(pronto)
    assert [c for c in comandos if "--collection-group=lembretes" in c] == []
    assert any("--collection-group=acoes" in c for c in comandos)
    assert not nuvem._m_indices(pronto).pronto  # construindo não é pronto


# --- as mãos e o agendador (Sessão 11, D61) -----------------------------------------------------


def test_contas_cria_as_maos_e_o_dono_pede_o_token_das_duas(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_ler", lambda _c: None)  # nada existe
    comandos = nuvem._c_contas(ctx)
    criadas = [c[4] for c in comandos if c[1:4] == ["iam", "service-accounts", "create"]]
    assert criadas == ["viking-motor", "viking-cli", "viking-maos"]
    papeis = [c for c in comandos if "--role=roles/iam.serviceAccountTokenCreator" in c]
    assert [(c[4], c[5]) for c in papeis] == [
        (f"viking-{nome}@viking-teste.iam.gserviceaccount.com", "--member=user:dono@example.com")
        for nome in ("cli", "maos")
    ]
    assert not any("agendador" in a for c in comandos for a in c)  # só no passo dele


def test_contas_sem_o_dono_no_token_das_maos_nao_esta_pronta(nuvem, ctx, monkeypatch):
    def politica(papel, membro):
        return {"bindings": [{"role": papel, "members": [membro]}]}

    gravador = _Gravador(
        {
            "iam service-accounts describe": {"email": "x"},
            "projects get-iam-policy": politica(
                "roles/datastore.user",
                "serviceAccount:viking-motor@viking-teste.iam.gserviceaccount.com",
            ),
            "iam service-accounts get-iam-policy viking-cli": politica(
                "roles/iam.serviceAccountTokenCreator", "user:dono@example.com"
            ),
            "iam service-accounts get-iam-policy viking-maos": {"bindings": []},
        }
    )
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    estado = nuvem._m_contas(ctx)
    assert (
        not estado.pronto and estado.detalhe == "o dono ainda não pode pedir token do viking-maos@"
    )


@pytest.mark.parametrize(
    ("quem", "certo"),
    [
        ({"cli", "maos"}, True),
        ({"cli", "maos", "agendador"}, True),
        ({"cli", "maos", "agendador", "casa"}, True),
        ({"cli", "maos", "casa"}, True),
        ({"casa"}, False),
        ({"cli"}, False),
        ({"maos", "agendador"}, False),
        ({"cli", "maos", "motor"}, False),
        ({"cli", "maos", "allUsers"}, False),
    ],
)
def test_so_o_terminal_as_maos_e_o_agendador_invocam(nuvem, ctx, quem, certo):
    membros = {
        "allUsers" if nome == "allUsers" else f"serviceAccount:{ctx.conta(f'viking-{nome}')}"
        for nome in quem
    }
    assert nuvem._invocadores_certos(ctx, membros) is certo


URL_DO_MOTOR = "https://motor-42.southamerica-east1.run.app"


def _tarefa(**mudancas):
    tarefa = {
        "schedule": "* * * * *",
        "state": "ENABLED",
        "httpTarget": {
            "uri": f"{URL_DO_MOTOR}/tarefas/lembretes",
            "httpMethod": "POST",
            "oidcToken": {
                "serviceAccountEmail": "viking-agendador@viking-teste.iam.gserviceaccount.com",
                "audience": URL_DO_MOTOR,
            },
        },
    }
    tarefa.update(mudancas)
    return tarefa


def _agendador(api=True, conta=True, invoca=True, tarefa=None):
    respostas = {
        "projects describe": {"projectNumber": "42"},
        "services list": [{"config": {"name": "cloudscheduler.googleapis.com"}}] if api else [],
    }
    if conta:
        respostas["iam service-accounts describe viking-agendador"] = {"email": "x"}
    membro = "serviceAccount:viking-agendador@viking-teste.iam.gserviceaccount.com"
    respostas["run services get-iam-policy motor"] = {
        "bindings": [{"role": "roles/run.invoker", "members": [membro] if invoca else []}]
    }
    if tarefa is not None:
        respostas["scheduler jobs describe viking-lembretes"] = tarefa
    return _Gravador(respostas)


@pytest.mark.parametrize(
    ("estado", "pronto", "trecho"),
    [
        ({"api": False}, False, "API do Cloud Scheduler desligada"),
        ({"conta": False}, False, "falta o agendador@"),
        ({"invoca": False}, False, "ainda não invoca"),
        ({}, False, "falta a tarefa"),
        ({"tarefa": _tarefa(schedule="*/5 * * * *")}, False, "a cada minuto"),
        ({"tarefa": _tarefa(state="PAUSED")}, False, "ligada"),
        (
            {"tarefa": _tarefa(httpTarget={**_tarefa()["httpTarget"], "oidcToken": {}})},
            False,
            "como o agendador@, com a audience do motor",
        ),
        ({"tarefa": _tarefa()}, True, "a cada minuto, como agendador@"),
    ],
)
def test_o_agendador_so_esta_pronto_com_tudo_certo(nuvem, ctx, monkeypatch, estado, pronto, trecho):
    monkeypatch.setattr(nuvem, "_rodar", _agendador(**estado))
    medido = nuvem._m_agendador(ctx)
    assert medido.pronto is pronto and trecho in medido.detalhe


def test_a_tarefa_do_agendador_chama_so_a_rota_do_envio_com_oidc(nuvem, ctx, monkeypatch):
    gravador = _agendador(conta=False)
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    pronto = nuvem.Contexto(**{**ctx.__dict__, "prontos": frozenset({"apis", "contas"})})
    ligar, criar, invocar, tarefa = nuvem._c_agendador(pronto)
    assert ligar[1:4] == ["services", "enable", "cloudscheduler.googleapis.com"]
    assert criar[1:5] == ["iam", "service-accounts", "create", "viking-agendador"]
    conta = "viking-agendador@viking-teste.iam.gserviceaccount.com"
    assert f"--member=serviceAccount:{conta}" in invocar and "--role=roles/run.invoker" in invocar
    assert tarefa[1:6] == ["scheduler", "jobs", "create", "http", "viking-lembretes"]
    for opcao in (
        "--schedule=* * * * *",
        f"--uri={URL_DO_MOTOR}/tarefas/lembretes",
        "--http-method=POST",
        f"--oidc-service-account-email={conta}",
        f"--oidc-token-audience={URL_DO_MOTOR}",
        "--location=southamerica-east1",
    ):
        assert opcao in tarefa, opcao
    assert not any(a.startswith(("--headers", "--message-body", "--oauth")) for a in tarefa)
    assert not any(_verbo(c) in _ESCRITAS for c in gravador.comandos)  # montar não escreve


def test_o_agendador_vem_antes_do_backup_e_sem_flag_nada_e_criado(nuvem):
    (passo,) = [p for p in nuvem.PASSOS if p.nome == "agendador"]
    nomes = [p.nome for p in nuvem.PASSOS]
    assert nomes.index("agendador") < nomes.index("backup") and "contas" in passo.depende
    assert "só para a conta do dono" in passo.irreversivel and "US$" in passo.irreversivel


# --- o passo do backup (Sessão 11c, D63) --------------------------------------------------------


def _tarefa_do_backup(**mudancas):
    tarefa = _tarefa(schedule="0 9 * * *")
    tarefa["httpTarget"] = {**tarefa["httpTarget"], "uri": f"{URL_DO_MOTOR}/tarefas/backup"}
    tarefa.update(mudancas)
    return tarefa


def _backup(versoes=1, tarefa=None):
    gravador = _agendador(tarefa=None)
    gravador.respostas["secrets versions list viking-drive"] = [{"name": "v"}] * versoes
    if tarefa is not None:
        gravador.respostas["scheduler jobs describe viking-backup"] = tarefa
    return gravador


@pytest.mark.parametrize(
    ("estado", "pronto", "trecho"),
    [
        ({"versoes": 0}, False, "o token do Drive ainda não subiu"),
        ({}, False, "falta a tarefa"),
        ({"tarefa": _tarefa_do_backup(schedule="* * * * *")}, False, "todo dia às 09:00 UTC"),
        ({"tarefa": _tarefa()}, False, "POST na rota do backup"),
        ({"tarefa": _tarefa_do_backup(state="PAUSED")}, False, "ligada"),
        ({"tarefa": _tarefa_do_backup()}, True, "só na rota do backup"),
    ],
)
def test_o_backup_so_esta_pronto_com_o_token_e_a_tarefa_certa(
    nuvem, ctx, monkeypatch, estado, pronto, trecho
):
    monkeypatch.setattr(nuvem, "_rodar", _backup(**estado))
    medido = nuvem._m_backup(ctx)
    assert medido.pronto is pronto and trecho in medido.detalhe


def test_a_tarefa_do_backup_chama_so_a_rota_dele_e_roda_uma_vez(nuvem, ctx, monkeypatch):
    gravador = _backup()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    pronto = nuvem.Contexto(**{**ctx.__dict__, "prontos": frozenset({"apis", "agendador"})})
    criar, rodar = nuvem._c_backup(pronto)
    assert criar[1:6] == ["scheduler", "jobs", "create", "http", "viking-backup"]
    conta = "viking-agendador@viking-teste.iam.gserviceaccount.com"
    for opcao in (
        "--schedule=0 9 * * *",
        "--time-zone=Etc/UTC",
        f"--uri={URL_DO_MOTOR}/tarefas/backup",
        "--http-method=POST",
        f"--oidc-service-account-email={conta}",
        f"--oidc-token-audience={URL_DO_MOTOR}",
        "--max-retry-attempts=0",
    ):
        assert opcao in criar, opcao
    assert rodar[1:5] == ["scheduler", "jobs", "run", "viking-backup"]
    assert not any(_verbo(c) in _ESCRITAS for c in gravador.comandos)  # montar não escreve


def test_com_a_tarefa_ja_criada_o_passo_so_roda_o_backup(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_rodar", _backup(tarefa=_tarefa_do_backup()))
    pronto = nuvem.Contexto(**{**ctx.__dict__, "prontos": frozenset({"apis", "agendador"})})
    (rodar,) = nuvem._c_backup(pronto)
    assert rodar[1:5] == ["scheduler", "jobs", "run", "viking-backup"]


def test_o_backup_vem_depois_do_agendador_e_diz_que_nunca_apaga(nuvem):
    (passo,) = [p for p in nuvem.PASSOS if p.nome == "backup"]
    assert passo.depende == ("agendador",)
    assert "nunca apaga" in passo.irreversivel and "US$" in passo.irreversivel


def test_a_prova_do_ultimo_backup_e_a_regua_de_48_horas(nuvem):
    from datetime import UTC, datetime, timedelta

    agora = datetime(2026, 10, 9, 12, tzinfo=UTC)
    assert nuvem._prova_do_ultimo_backup((agora - timedelta(hours=47)).isoformat(), agora).passou
    assert not nuvem._prova_do_ultimo_backup(
        (agora - timedelta(hours=49)).isoformat(), agora
    ).passou
    assert not nuvem._prova_do_ultimo_backup(None, agora).passou


# --- o token do Drive sobe do Mac, como o do Gmail (Sessão 11c, D63) ----------------------------


def test_deploy_sem_o_token_do_drive_publica_sem_ele(nuvem, ctx, mundo, capsys):
    m = mundo(vazios={"viking-drive"})
    assert nuvem.deploy(ctx, executar=True) == 0
    segredos, variaveis = _implantado(m)
    assert "viking-drive" not in segredos and "viking-gmail" in segredos
    assert "VIKING_DRIVE_TOKEN_ARQUIVO" not in variaveis
    assert "Fora desta revisão (sem versão; sobe do Mac): viking-drive" in capsys.readouterr().out


def test_com_o_token_do_drive_publica_com_ele(nuvem, ctx, mundo):
    m = mundo()
    assert nuvem.deploy(ctx, executar=True) == 0
    segredos, variaveis = _implantado(m)
    assert "/segredos/drive/token.json=viking-drive:latest" in segredos
    assert "VIKING_DRIVE_TOKEN_ARQUIVO=/segredos/drive/token.json" in variaveis


def _token_do_drive(tmp_path, monkeypatch, **mudancas):
    from lifeos import config

    info = {
        "refresh_token": REFRESH_FALSO,
        "client_id": "cliente",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
        **mudancas,
    }
    arquivo = tmp_path / "google_token_drive.json"
    arquivo.write_text(json.dumps(info))
    monkeypatch.setattr(config, "DRIVE_TOKEN_PATH", arquivo)
    return arquivo.read_text()


def test_o_token_do_drive_sobe_pela_entrada_padrao_e_nunca_aparece(
    nuvem, ctx, monkeypatch, capsys, tmp_path
):
    texto = _token_do_drive(tmp_path, monkeypatch)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    assert nuvem.segredo(ctx, "viking-drive", executar=True) == 0
    ((comando, entrada),) = [(c, e) for c, e in g.chamadas if "add" in c]
    assert "viking-drive" in comando and "--data-file=-" in comando and entrada == texto
    assert REFRESH_FALSO not in capsys.readouterr().out


@pytest.mark.parametrize(
    "mudanca",
    [{"scopes": ["https://www.googleapis.com/auth/gmail.modify"]}, {"refresh_token": ""}],
    ids=["sem-o-escopo-do-drive", "sem-renovacao"],
)
def test_token_do_drive_torto_nao_sobe_nem_aparece(
    nuvem, ctx, monkeypatch, capsys, tmp_path, mudanca
):
    _token_do_drive(tmp_path, monkeypatch, **mudanca)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    with pytest.raises(SystemExit, match="nada foi enviado") as erro:
        nuvem.segredo(ctx, "viking-drive", executar=True)
    assert not any("add" in c for c, _ in g.chamadas)
    assert REFRESH_FALSO not in str(erro.value) + capsys.readouterr().out


# --- o serviço de finanças (Sessão 11d, D64) ---------------------------------------------------

MOTOR_SA = "serviceAccount:viking-motor@viking-teste.iam.gserviceaccount.com"
FINANCAS_SA = "serviceAccount:viking-financas@viking-teste.iam.gserviceaccount.com"
ITEM = "0f8c2a3e-1b2c-4d5e-8f90-123456789abc"
SEGREDO_DA_PLUGGY = "segredo-da-pluggy-nao-pode-vazar"


def _leitura(*membros):
    return {"bindings": [{"role": "roles/secretmanager.secretAccessor", "members": list(membros)}]}


def test_o_passo_das_financas_cria_so_o_que_falta_e_so_o_financas_le(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_ler", lambda _c: None)  # nada existe
    pronto = nuvem.dataclasses.replace(ctx, prontos=frozenset({"apis", "contas"}))
    comandos = nuvem._c_financas(pronto)
    assert [c[1:5] for c in comandos] == [
        ["iam", "service-accounts", "create", "viking-financas"],
        ["secrets", "create", "viking-pluggy", "--replication-policy=automatic"],
        ["secrets", "add-iam-policy-binding", "viking-pluggy", f"--member={FINANCAS_SA}"],
    ]
    assert not any("viking-motor" in a for c in comandos for a in c)
    # quase tudo existe (a segunda vida do passo, erros classe 7): só a leitura, idempotente
    monkeypatch.setattr(nuvem, "_ler", lambda _c: {"name": "x"})
    (so_a_leitura,) = nuvem._c_financas(pronto)
    assert so_a_leitura[1:3] == ["secrets", "add-iam-policy-binding"]


@pytest.mark.parametrize(
    ("leem", "pronto"),
    [
        ((FINANCAS_SA,), True),
        ((FINANCAS_SA, MOTOR_SA), False),
        ((MOTOR_SA,), False),
        ((), False),
    ],
)
def test_a_medida_reprova_quem_mais_le_o_segredo_da_pluggy(nuvem, ctx, monkeypatch, leem, pronto):
    g = _Gravador(
        {
            "iam service-accounts describe": {"email": "x"},
            "secrets describe viking-pluggy": {"name": "x"},
            "secrets get-iam-policy viking-pluggy": _leitura(*leem),
            "secrets versions list viking-pluggy": [],
        }
    )
    monkeypatch.setattr(nuvem, "_rodar", g)
    estado = nuvem._m_financas(ctx)
    assert estado.pronto is pronto
    if pronto:
        assert "vazio (sobe do Mac" in estado.detalhe


def test_o_passo_das_financas_nao_toca_o_motor(nuvem):
    (passo,) = [p for p in nuvem.PASSOS if p.nome == "financas"]
    assert set(passo.depende) == {"apis", "contas"}
    assert nuvem.SEGREDO_DAS_FINANCAS not in nuvem.SEGREDOS
    assert nuvem.SEGREDO_DAS_FINANCAS in nuvem.TODOS_OS_SEGREDOS


def _deploys(m):
    return [c for c in m.gcloud if c[1:3] == ["run", "deploy"]]


def test_com_o_segredo_da_pluggy_publica_as_financas_antes_do_motor(nuvem, ctx, mundo):
    m = mundo(financas=True)
    assert nuvem.deploy(ctx, executar=True) == 0
    financas, motor = _deploys(m)
    assert financas[3] == "financas" and motor[3] == "motor"
    assert m.gcloud.index(financas) < m.gcloud.index(motor)
    for esperado in (
        "--service-account=viking-financas@viking-teste.iam.gserviceaccount.com",
        "--no-allow-unauthenticated",
        "--max-instances=1",
        "--command=/app/.venv/bin/uvicorn",
        "--args=lifeos.nuvem.financas:app,--host,0.0.0.0,--port,8080,--no-access-log",
        "--set-secrets=/segredos/pluggy/credenciais.json=viking-pluggy:latest",
    ):
        assert esperado in financas, esperado
    assert financas[4] == motor[4]  # a mesma imagem
    (variaveis,) = [a for a in financas if a.startswith("--set-env-vars=")]
    assert "VIKING_NUVEM_URL=https://financas-42.southamerica-east1.run.app" in variaveis
    assert "VIKING_PLUGGY_ARQUIVO=/segredos/pluggy/credenciais.json" in variaveis
    assert "GEMINI" not in variaveis and "FINANCAS_URL" not in variaveis
    (invoca,) = [
        c
        for c in m.gcloud
        if c[1:4] == ["run", "services", "add-iam-policy-binding"] and c[4] == "financas"
    ]
    assert f"--member={MOTOR_SA}" in invoca and "--role=roles/run.invoker" in invoca
    (do_motor,) = [a for a in motor if a.startswith("--set-env-vars=")]
    assert "VIKING_FINANCAS_URL=https://financas-42.southamerica-east1.run.app" in do_motor
    (segredos_do_motor,) = [a for a in motor if a.startswith("--set-secrets=")]
    assert "viking-pluggy" not in segredos_do_motor and "PLUGGY" not in do_motor


def test_sem_o_segredo_da_pluggy_so_o_motor_e_sem_a_url(nuvem, ctx, mundo, capsys):
    m = mundo()
    assert nuvem.deploy(ctx, executar=True) == 0
    (motor,) = _deploys(m)
    assert motor[3] == "motor" and not any("FINANCAS" in a for a in motor)
    assert not any("financas" in a for c in m.gcloud for a in c[:5])
    assert "viking-pluggy (sem ele, o serviço de finanças)" in capsys.readouterr().out


def test_o_segredo_da_pluggy_que_subiu_pede_revisao_mesmo_sem_codigo_novo(nuvem, ctx, mundo):
    m = mundo(no_ar=SHA, financas=True, financas_no_ar=False)
    assert nuvem.deploy(ctx, executar=True) == 0
    assert [c[3] for c in _deploys(m)] == ["financas", "motor"]
    m = mundo(no_ar=SHA, financas=True, financas_no_ar=True)
    assert nuvem.deploy(ctx, executar=True) == 0
    assert _deploys(m) == []


def _env_da_pluggy(monkeypatch, client_id="id-do-app", ids=(ITEM,)):
    from lifeos import config

    monkeypatch.setattr(config, "PLUGGY_CLIENT_ID", client_id)
    monkeypatch.setattr(config, "PLUGGY_CLIENT_SECRET", SEGREDO_DA_PLUGGY)
    monkeypatch.setattr(config, "PLUGGY_ITEM_IDS", ids)


def test_o_segredo_da_pluggy_sobe_pela_entrada_padrao_e_nunca_aparece(
    nuvem, ctx, monkeypatch, capsys
):
    _env_da_pluggy(monkeypatch)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    assert nuvem.segredo(ctx, "viking-pluggy", executar=True) == 0
    ((comando, entrada),) = [(c, e) for c, e in g.chamadas if "add" in c]
    assert "viking-pluggy" in comando and "--data-file=-" in comando
    assert json.loads(entrada) == {
        "client_id": "id-do-app",
        "client_secret": SEGREDO_DA_PLUGGY,
        "item_ids": [ITEM],
    }
    assert all(SEGREDO_DA_PLUGGY not in " ".join(c) for c, _ in g.chamadas)
    assert SEGREDO_DA_PLUGGY not in capsys.readouterr().out


@pytest.mark.parametrize(
    "mudanca",
    [{"ids": ()}, {"ids": ("0f8c2a3e",)}, {"client_id": ""}],
)
def test_o_env_sem_conexoes_ou_torto_nao_sobe(nuvem, ctx, monkeypatch, capsys, mudanca):
    """No VPS o `.env` não tem os IDs (medido em 2026-10-07): o segredo sobe do Mac."""
    _env_da_pluggy(monkeypatch, **mudanca)
    g = _Gcloud()
    monkeypatch.setattr(nuvem, "_rodar", g.rodar)
    with pytest.raises(SystemExit, match="nada foi enviado") as erro:
        nuvem.segredo(ctx, "viking-pluggy", executar=True)
    assert not any("add" in c for c, _ in g.chamadas)
    assert SEGREDO_DA_PLUGGY not in str(erro.value) + capsys.readouterr().out


# --- as provas das finanças, sem a Pluggy ------------------------------------------------------


class _Resposta:
    def __init__(self, status, corpo):
        self.status_code = status
        self.text = corpo if isinstance(corpo, str) else json.dumps(corpo)

    def json(self):
        return json.loads(self.text)


def _servico_das_financas(**mudancas):
    conteiner = {
        "image": f"southamerica-east1-docker.pkg.dev/viking-teste/viking/motor:{SHA}",
        "command": ["/app/.venv/bin/uvicorn"],
        "args": [
            "lifeos.nuvem.financas:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--no-access-log",
        ],
        "env": [
            {"name": "VIKING_NUVEM_PROJETO", "value": "viking-teste"},
            {"name": "VIKING_NUVEM_URL", "value": "https://financas-42.x"},
            {"name": "VIKING_TIMEZONE", "value": "America/Los_Angeles"},
            {"name": "VIKING_PLUGGY_ARQUIVO", "value": "/segredos/pluggy/credenciais.json"},
        ],
    }
    conteiner.update(mudancas.pop("conteiner", {}))
    modelo = {
        "serviceAccountName": "viking-financas@viking-teste.iam.gserviceaccount.com",
        "containers": [conteiner],
        "volumes": [{"name": "viking-pluggy", "secret": {"secretName": "viking-pluggy"}}],
    }
    modelo.update(mudancas)
    return {"spec": {"template": {"spec": modelo}}}


def _provas_das_financas(
    nuvem, ctx, monkeypatch, *, servico=None, invocam=(MOTOR_SA,), leem=(FINANCAS_SA,), fumaca=None
):
    import requests

    respostas = {
        "projects describe": {"projectNumber": "42"},
        "run services describe financas": servico or _servico_das_financas(),
        "run services get-iam-policy financas": {
            "bindings": [{"role": "roles/run.invoker", "members": list(invocam)}]
        },
        "secrets get-iam-policy viking-pluggy": _leitura(*leem),
        "logging read": [],
    }

    def ler(comando):
        chave = " ".join(a for a in comando[1:] if not a.startswith("--"))
        return next((v for k, v in respostas.items() if chave.startswith(k)), None)

    monkeypatch.setattr(nuvem, "_ler", ler)
    monkeypatch.setattr(
        nuvem,
        "_token",
        lambda _ctx, *a: "TOKEN-CLI" if any("viking-cli@" in x for x in a) else "TOKEN-DONO",
    )
    monkeypatch.setattr(nuvem, "_fuso", lambda: "America/Los_Angeles")
    chamadas = []

    def post(url, **_k):
        chamadas.append(url)
        if _k.get("headers", {}).get("Authorization") == "Bearer TOKEN-DONO":
            return _Resposta(401, "token recusado")  # o dono passa no IAM; o código recusa
        return _Resposta(403, "<html>Forbidden</html>")  # sem token, ou o cli@: o Google

    def get(url, **_k):
        chamadas.append(url)
        return _Resposta(200, fumaca or {"commit": SHA, "credenciais": True, "conexoes": 2})

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    return {p.nome: p for p in nuvem._provas_das_financas(ctx, SHA, URL_DO_MOTOR, {})}, chamadas


def test_as_provas_das_financas_passam_no_certo_e_nao_chamam_a_pluggy(nuvem, ctx, monkeypatch):
    provas_, chamadas = _provas_das_financas(nuvem, ctx, monkeypatch)
    assert [n for n, p in provas_.items() if not p.passou] == []
    assert len(provas_) == 12  # a 12ª: o fuso (14b)
    assert all("pluggy.ai" not in url for url in chamadas)
    assert f"{URL_DO_MOTOR}/fumaca/financas" in chamadas


def test_a_prova_do_fuso_das_financas_pega_o_fuso_velho(nuvem, ctx, monkeypatch):
    env = [
        e if e["name"] != "VIKING_TIMEZONE" else {"name": "VIKING_TIMEZONE", "value": "UTC"}
        for e in _servico_das_financas()["spec"]["template"]["spec"]["containers"][0]["env"]
    ]
    servico = _servico_das_financas(conteiner={"env": env})
    provas_, _ = _provas_das_financas(nuvem, ctx, monkeypatch, servico=servico)
    assert not provas_["finanças: o fuso no ar = o do .env"].passou


@pytest.mark.parametrize(
    ("caso", "mudanca", "prova"),
    [
        ("o motor@ lê o segredo", {"leem": (FINANCAS_SA, MOTOR_SA)}, "viking-pluggy: só o"),
        (
            "o cli@ invoca",
            {"invocam": (MOTOR_SA, MOTOR_SA.replace("motor", "cli"))},
            "finanças: só o viking-motor@ invoca",
        ),
        (
            "outra conta",
            {"servico": _servico_das_financas(serviceAccountName="x@y")},
            "finanças: a conta é o viking-financas@",
        ),
        (
            "o comando do motor",
            {"servico": _servico_das_financas(conteiner={"command": [], "args": []})},
            "finanças: roda o app de finanças",
        ),
        (
            "a chave do Gemini junto",
            {
                "servico": _servico_das_financas(
                    volumes=[
                        {"name": "viking-pluggy", "secret": {"secretName": "viking-pluggy"}},
                        {"name": "viking-gemini", "secret": {"secretName": "viking-gemini"}},
                    ]
                )
            },
            "finanças: só o segredo da Pluggy, como volume",
        ),
        (
            "sem credenciais",
            {"fumaca": {"commit": SHA, "credenciais": False, "conexoes": 0}},
            "viking-cli@: /fumaca/financas (o serviço lê as credenciais, sem chamar a Pluggy)",
        ),
    ],
)
def test_as_provas_das_financas_reprovam_o_errado(nuvem, ctx, monkeypatch, caso, mudanca, prova):
    provas_, _ = _provas_das_financas(nuvem, ctx, monkeypatch, **mudanca)
    (achada,) = [p for n, p in provas_.items() if n.startswith(prova)]
    assert not achada.passou, caso


def test_dar_papel_a_conta_recem_criada_espera_a_propagacao(nuvem, monkeypatch):
    """Medido no passo `financas` (2026-10-07): o IAM ainda não enxergava a conta recém-criada."""
    respostas = [
        subprocess.CompletedProcess([], 1, "", "ERROR: Service account x does not exist.."),
        subprocess.CompletedProcess([], 0, "", ""),
    ]
    chamadas, esperas = [], []
    monkeypatch.setattr(nuvem, "_rodar", lambda c: chamadas.append(c) or respostas.pop(0))
    monkeypatch.setattr(nuvem.time, "sleep", esperas.append)
    comando = ["gcloud", "secrets", "add-iam-policy-binding", "s", "--project=viking-teste"]
    assert nuvem._rodar_esperando_a_conta(comando).returncode == 0
    assert len(chamadas) == 2 and esperas == [15]


@pytest.mark.parametrize(
    ("comando", "erro"),
    [
        (["gcloud", "secrets", "add-iam-policy-binding", "s"], "PERMISSION_DENIED"),
        (["gcloud", "secrets", "create", "s"], "Service account x does not exist"),
    ],
)
def test_outro_erro_ou_outro_comando_nao_espera(nuvem, monkeypatch, comando, erro):
    chamadas = []
    monkeypatch.setattr(
        nuvem,
        "_rodar",
        lambda c: chamadas.append(c) or subprocess.CompletedProcess(c, 1, "", erro),
    )
    monkeypatch.setattr(nuvem.time, "sleep", lambda _s: pytest.fail("esperou"))
    assert nuvem._rodar_esperando_a_conta(comando).returncode == 1
    assert len(chamadas) == 1


def test_a_prova_do_chat_confere_a_busca_e_os_modelos_da_arvore(nuvem):
    """Sessão 12 (D65): o `/versao` no ar tem de dizer a busca e os modelos desta árvore; um motor
    antigo (sem os campos) ou com outro modelo reprova."""
    from lifeos.assistant import turno

    certo = {
        "busca": True,
        "modelo": turno.MODELO,
        "forte": turno.MODELO_FORTE,
        "memoria": True,
        "receitas": True,
        "documentos": True,
        "gmail": True,
    }
    assert nuvem._prova_do_chat(certo).passou
    assert not nuvem._prova_do_chat(certo | {"receitas": None}).passou  # um motor de antes da 13b
    assert not nuvem._prova_do_chat(certo | {"documentos": None}).passou  # um de antes da 14
    assert not nuvem._prova_do_chat(certo | {"memoria": False}).passou  # a 13 desligada no ar
    assert not nuvem._prova_do_chat({"commit": "velho", "gmail": True}).passou
    assert not nuvem._prova_do_chat(certo | {"modelo": "gemini-2.5-flash"}).passou
    assert not nuvem._prova_do_chat(certo | {"forte": "gemini-3.1-pro-preview"}).passou


# --- o editor da conta padrão e os alertas (Sessão 14b, D69) -----------------------------------

COMPUTE = "serviceAccount:42-compute@developer.gserviceaccount.com"


def _iam_do_projeto(*com_editor):
    return {"bindings": [{"role": "roles/editor", "members": list(com_editor)}]}


def test_o_editor_da_conta_padrao_e_medido_e_removido_so_dela(nuvem, ctx, monkeypatch):
    gravador = _Gravador(
        {
            "projects describe": {"projectNumber": "42"},
            "projects get-iam-policy": _iam_do_projeto(COMPUTE, "user:dono@example.com"),
        }
    )
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert not nuvem._m_editor(ctx).pronto
    (comando,) = nuvem._c_editor(dataclasses.replace(ctx, prontos=frozenset({"contas"})))
    assert comando[:3] == ["gcloud", "projects", "remove-iam-policy-binding"]
    assert f"--member={COMPUTE}" in comando and "--role=roles/editor" in comando
    assert not any("dono@" in a for a in comando)


def test_sem_o_editor_o_passo_esta_pronto(nuvem, ctx, monkeypatch):
    gravador = _Gravador(
        {
            "projects describe": {"projectNumber": "42"},
            "projects get-iam-policy": _iam_do_projeto("user:dono@example.com"),
        }
    )
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert nuvem._m_editor(ctx).pronto


CANAL = "projects/viking-teste/notificationChannels/7"
AGORA = datetime(2026, 11, 21, 21, 0, tzinfo=UTC)


def _metrica(nuvem, criada_ha_s):
    criada = (AGORA - timedelta(seconds=criada_ha_s)).isoformat().replace("+00:00", "Z")
    return {
        "name": nuvem.METRICA_DO_AGENDADOR,
        "filter": nuvem.FILTRO_DO_SUCESSO,
        "createTime": criada,
    }


def _canal(email="dono@example.com"):
    return {
        "name": CANAL,
        "displayName": "viking: o e-mail do dono",
        "type": "email",
        "labels": {"email_address": email},
    }


def _alertas(nuvem, ctx, monkeypatch, respostas):
    monkeypatch.setattr(nuvem, "_rodar", _Gravador(respostas))
    return dataclasses.replace(ctx, prontos=frozenset({"backup"}))


def test_alertas_do_zero_criam_a_metrica_e_o_canal_antes_das_politicas(nuvem, ctx, monkeypatch):
    pronto = _alertas(nuvem, ctx, monkeypatch, {})
    comandos = nuvem._c_alertas(pronto, agora=AGORA)
    assert [c[1:4] for c in comandos] == [
        ["logging", "metrics", "create"],
        ["beta", "monitoring", "channels"],
    ]
    assert f"--log-filter={nuvem.FILTRO_DO_SUCESSO}" in comandos[0]
    assert "--channel-labels=email_address=dono@example.com" in comandos[1]
    assert "faltam" in nuvem._m_alertas(pronto).detalhe


@pytest.mark.parametrize(
    ("idade_s", "esperadas"),
    [
        (60, []),  # antes de 15 min, "nenhum dado" seria um alerta falso
        (20 * 60, ["viking-lembretes"]),
        (26 * 3600, ["viking-lembretes", "viking-backup"]),
    ],
)
def test_cada_politica_so_nasce_depois_da_janela_dela(nuvem, ctx, monkeypatch, idade_s, esperadas):
    pronto = _alertas(
        nuvem,
        ctx,
        monkeypatch,
        {
            "logging metrics describe": _metrica(nuvem, idade_s),
            "beta monitoring channels list": [_canal()],
            "monitoring policies list": [],
        },
    )
    comandos = nuvem._c_alertas(pronto, agora=AGORA)
    politicas = [
        json.loads(a.removeprefix("--policy="))
        for c in comandos
        for a in c
        if a.startswith("--policy=")
    ]
    assert [
        p["conditions"][0]["conditionThreshold"]["filter"].rsplit('"', 2)[-2] for p in politicas
    ] == esperadas
    for politica in politicas:
        assert politica["notificationChannels"] == [CANAL]
        assert "dono@example.com" not in json.dumps(politica)  # o e-mail só no canal


def test_o_canal_de_outro_e_mail_nao_conta(nuvem, ctx, monkeypatch):
    pronto = _alertas(
        nuvem,
        ctx,
        monkeypatch,
        {
            "logging metrics describe": _metrica(nuvem, 30 * 3600),
            "beta monitoring channels list": [_canal("outro@example.com")],
            "monitoring policies list": [],
        },
    )
    assert any("channels" in c for c in nuvem._c_alertas(pronto, agora=AGORA))


def _politicas_certas(nuvem):
    return [nuvem._politica(t, o, j, d, CANAL) for t, o, j, d in nuvem.VIGIADAS]


def test_alertas_completos_estao_prontos_e_nao_recriam_nada(nuvem, ctx, monkeypatch):
    pronto = _alertas(
        nuvem,
        ctx,
        monkeypatch,
        {
            "logging metrics describe": _metrica(nuvem, 30 * 3600),
            "beta monitoring channels list": [_canal()],
            "monitoring policies list": _politicas_certas(nuvem),
        },
    )
    assert nuvem._m_alertas(pronto).pronto
    assert nuvem._c_alertas(pronto, agora=AGORA) == []


@pytest.mark.parametrize(
    "estraga",
    [
        lambda p: p.update(enabled=False),
        lambda p: p["conditions"][0]["conditionThreshold"]["aggregations"][0].update(
            alignmentPeriod="60s"
        ),
        lambda p: p["conditions"][0]["conditionThreshold"].update(
            evaluationMissingData="EVALUATION_MISSING_DATA_INACTIVE"
        ),
        lambda p: p.update(notificationChannels=[]),
        lambda p: p["conditions"][0]["conditionThreshold"].update(duration="60s"),
        lambda p: p["conditions"][0]["conditionThreshold"].update(filter='metric.type="x"'),
    ],
)
def test_politica_torta_nao_conta_como_pronta(nuvem, ctx, monkeypatch, estraga):
    politicas = _politicas_certas(nuvem)
    estraga(politicas[1])
    pronto = _alertas(
        nuvem,
        ctx,
        monkeypatch,
        {
            "logging metrics describe": _metrica(nuvem, 30 * 3600),
            "beta monitoring channels list": [_canal()],
            "monitoring policies list": politicas,
        },
    )
    assert not nuvem._m_alertas(pronto).pronto


def test_a_janela_do_backup_cabe_no_limite_e_cobre_um_dia(nuvem):
    total = {t: j + d for t, _o, j, d in nuvem.VIGIADAS}
    assert 24 * 3600 < total["viking-backup"] <= 90_000  # uma métrica de log alerta sobre 25 h
    assert total["viking-lembretes"] >= 5 * 60  # um minuto perdido (502) não é alarme


def test_sem_dado_como_alarme_pede_duracao(nuvem):
    """A API recusou a 1ª política (2026-11-21 21:35Z): `EVALUATION_MISSING_DATA_ACTIVE` "must
    have a non-zero duration"."""
    for tarefa, oque, janela, duracao in nuvem.VIGIADAS:
        limiar = nuvem._politica(tarefa, oque, janela, duracao, CANAL)["conditions"][0][
            "conditionThreshold"
        ]
        assert limiar["evaluationMissingData"] == "EVALUATION_MISSING_DATA_ACTIVE"
        assert int(limiar["duration"].removesuffix("s")) >= 60


# --- a ponte de casa da voz do estúdio (Sessão H1, D70) ----------------------------------------

CASA = "serviceAccount:viking-casa@viking-teste.iam.gserviceaccount.com"


def _mundo_da_casa(*, conta=True, papel=None, invoca=True, chaves=(), cortada=False):
    respostas = {
        "projects get-iam-policy": {
            "bindings": [{"role": papel, "members": [CASA]}] if papel else []
        },
        "run services get-iam-policy motor": {
            "bindings": [{"role": "roles/run.invoker", "members": [CASA] if invoca else []}]
        },
        "iam service-accounts keys list": [{"keyOrigin": o} for o in chaves],
    }
    if conta:
        respostas["iam service-accounts describe"] = {"disabled": cortada}
    return _Gravador(respostas)


@pytest.mark.parametrize(
    ("mundo", "pronto", "trecho"),
    [
        ({"conta": False}, False, "falta a conta"),
        ({"papel": "roles/editor"}, False, "papel no projeto"),
        ({"invoca": False}, False, "não invoca"),
        ({"chaves": ("GOOGLE_PROVIDED",)}, False, "não nasceram no laptop"),
        ({"chaves": ("USER_PROVIDED",) * 3}, False, "no máximo 2"),
        ({}, True, "sem chave ainda"),
        ({"chaves": ("USER_PROVIDED",)}, True, "1 chave(s) do laptop"),
        ({"chaves": ("USER_PROVIDED",), "cortada": True}, True, "CORTADA"),
    ],
)
def test_a_casa_e_medida(nuvem, ctx, monkeypatch, mundo, pronto, trecho):
    monkeypatch.setattr(nuvem, "_rodar", _mundo_da_casa(**mundo))
    estado = nuvem._m_casa(ctx)
    assert estado.pronto is pronto and trecho in estado.detalhe, estado.detalhe


def test_a_casa_nasce_sem_papel_no_projeto_e_so_invoca_o_motor(nuvem, ctx, monkeypatch):
    monkeypatch.setattr(nuvem, "_rodar", _Gravador())
    criar, invocar = nuvem._c_casa(dataclasses.replace(ctx, prontos=frozenset({"contas"})))
    assert criar[:5] == ["gcloud", "iam", "service-accounts", "create", "viking-casa"]
    assert invocar[:5] == ["gcloud", "run", "services", "add-iam-policy-binding", "motor"]
    assert "--role=roles/run.invoker" in invocar and f"--member={CASA}" in invocar
    assert not any(c[1] == "projects" for c in nuvem._c_casa(ctx))


def test_a_casa_depois_das_contas_e_por_ultimo(nuvem):
    (passo,) = [p for p in nuvem.PASSOS if p.nome == "casa"]
    assert passo.depende == ("contas",) and nuvem.PASSOS[-1] is passo


def _certificado(tmp_path, *, bits=2048, rsa_=True, com_privada=False):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.x509.oid import NameOID

    chave = (
        rsa.generate_private_key(public_exponent=65537, key_size=bits)
        if rsa_
        else ec.generate_private_key(ec.SECP256R1())
    )
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unused")])
    agora = datetime.now(UTC)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(1)
        .not_valid_before(agora)
        .not_valid_after(agora + timedelta(days=365))
        .sign(chave, hashes.SHA256())
    )
    pem = certificado.public_bytes(serialization.Encoding.PEM)
    if com_privada:
        pem += chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    arquivo = tmp_path / "casa-publica.pem"
    arquivo.write_bytes(pem)
    return arquivo


def test_o_certificado_do_laptop_e_conferido(nuvem, tmp_path):
    impressao = nuvem.conferir_certificado(_certificado(tmp_path))
    assert len(impressao.split(":")) == 32


@pytest.mark.parametrize(
    ("mudanca", "trecho"),
    [
        ({"com_privada": True}, "CHAVE PRIVADA"),
        ({"bits": 1024}, "2048"),
        ({"rsa_": False}, "RSA"),
    ],
)
def test_o_certificado_errado_e_recusado(nuvem, tmp_path, mudanca, trecho):
    with pytest.raises(ValueError, match=trecho):
        nuvem.conferir_certificado(_certificado(tmp_path, **mudanca))


def test_lixo_nao_e_certificado(nuvem, tmp_path):
    lixo = tmp_path / "x.pem"
    lixo.write_text("oi")
    with pytest.raises(ValueError, match="X.509"):
        nuvem.conferir_certificado(lixo)


def test_casa_chave_sem_executar_so_mostra(nuvem, ctx, monkeypatch, tmp_path, capsys):
    gravador = _mundo_da_casa()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert nuvem.casa_chave(ctx, _certificado(tmp_path), executar=False) == 0
    assert {_verbo(c) for c in gravador.comandos} <= _LEITURAS
    assert "Nada foi mudado" in capsys.readouterr().out


def test_casa_chave_sobe_o_arquivo_pelo_caminho(nuvem, ctx, monkeypatch, tmp_path):
    gravador = _mundo_da_casa()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    certificado = _certificado(tmp_path)
    nuvem.casa_chave(ctx, certificado, executar=True)
    (upload,) = [c for c in gravador.comandos if "upload" in c]
    assert str(certificado) in upload
    assert "--iam-account=viking-casa@viking-teste.iam.gserviceaccount.com" in upload
    assert not any("BEGIN" in a for a in upload)  # o conteúdo nunca no argv


def test_casa_chave_recusa_a_terceira(nuvem, ctx, monkeypatch, tmp_path):
    gravador = _mundo_da_casa(chaves=("USER_PROVIDED", "USER_PROVIDED"))
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert nuvem.casa_chave(ctx, _certificado(tmp_path), executar=True) == 1
    assert not any("upload" in c for c in gravador.comandos)


def test_casa_chave_com_a_privada_nao_sobe_nada(nuvem, ctx, monkeypatch, tmp_path):
    gravador = _mundo_da_casa()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert nuvem.casa_chave(ctx, _certificado(tmp_path, com_privada=True), executar=True) == 1
    assert gravador.comandos == []


@pytest.mark.parametrize(("religar", "verbo"), [(False, "disable"), (True, "enable")])
def test_o_corte_de_emergencia(nuvem, ctx, monkeypatch, religar, verbo):
    gravador = _Gravador()
    monkeypatch.setattr(nuvem, "_rodar", gravador)
    assert nuvem.casa_corte(ctx, religar, executar=False) == 0
    assert gravador.comandos == []
    assert nuvem.casa_corte(ctx, religar, executar=True) == 0
    (comando,) = gravador.comandos
    assert comando[1:4] == ["iam", "service-accounts", verbo]
    assert "viking-casa@viking-teste.iam.gserviceaccount.com" in comando


def test_main_leva_os_subcomandos_da_casa(nuvem, ctx, monkeypatch, tmp_path):
    vistos, contextos = [], []
    monkeypatch.setattr(nuvem, "_contexto", lambda **k: contextos.append(k) or ctx)
    monkeypatch.setattr(nuvem, "casa_corte", lambda _c, r, e: vistos.append(("corte", r, e)) or 0)
    monkeypatch.setattr(nuvem, "casa_chave", lambda _c, p, e: vistos.append(("chave", p, e)) or 0)
    nuvem.main(["casa-cortar", "--executar"])
    nuvem.main(["casa-religar"])
    nuvem.main(["casa-chave", str(tmp_path / "c.pem")])
    assert vistos == [
        ("corte", False, True),
        ("corte", True, False),
        ("chave", tmp_path / "c.pem", False),
    ]
    # Os três rodam no Mac também: só o projeto, nunca o faturamento nem o orçamento do VPS.
    assert contextos == [{"so_projeto": True}] * 3
