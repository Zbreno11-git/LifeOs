"""A infraestrutura do Viking no GCP, como script (Sessão 10, D58; skill `nuvem-e-deploy` §6).

**Sem flag, só lê:** mede cada passo no projeto de verdade e imprime o que existe, o que falta e o
comando que criaria. **Com `--executar PASSO`**, roda os comandos daquele passo e mede de novo.
O ok do dono vem antes, na conversa, passo a passo: criar recurso ou gastar é decisão dele.

    python scripts/nuvem.py                       (só lê)
    python scripts/nuvem.py --executar projeto    (um passo)
    python scripts/nuvem.py deploy                (o que está no ar, o que mudou, e as provas)
    python scripts/nuvem.py deploy --executar     (constrói, envia, publica e prova)
    python scripts/nuvem.py segredo NOME [--executar]  (mede; ou sobe a versão pela entrada padrão)
    python scripts/nuvem.py prova-chat [MENSAGEM]      (um turno real no ar: gasta, só quando pedido)

Roda com o login do `gcloud` do VPS, que é a conta do dono e alcança **todos** os projetos dele
(D47 revista, 2026-09-29). Por isso todo `gcloud` sai de `_gcloud`, que acrescenta
`--project=<o do Viking>` sempre; `tests/test_nuvem_script.py` reprova qualquer outro caminho até
o `gcloud`. O projeto padrão da configuração é outro projeto do dono e nunca é usado.

Valores do `.env` (nenhum no repo): `VIKING_NUVEM_PROJETO`, `VIKING_NUVEM_FATURAMENTO` (a conta de
faturamento), `VIKING_NUVEM_ORCAMENTO` (valor e moeda da conta, ex. `105BRL`); a região vem de
`config.NUVEM_REGIAO`. A saída não mostra token nem a conta de faturamento inteira.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lifeos import config, registro_firestore
from lifeos.reminders import store_firestore

APIS = (
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "billingbudgets.googleapis.com",
    "secretmanager.googleapis.com",  # a chave do Gemini e os tokens da agenda e do Gmail
)
REPOSITORIO = "viking"  # Artifact Registry
GUARDAR_IMAGENS = 5
ORCAMENTO_NOME = "viking"
ALERTAS = (0.5, 0.9, 1.0)
# Contas de serviço (o ID pede de 6 a 30 letras). O dono pede o token do `cli@` (o terminal) e do
# `maos@` (o `viking maos`, Sessão 11, D61); o do `agendador@` é o Cloud Scheduler que pede.
MOTOR, CLI, MAOS, AGENDADOR = "viking-motor", "viking-cli", "viking-maos", "viking-agendador"
DO_DONO = (CLI, MAOS)
# Os índices compostos que as consultas pedem, declarados por cada store (uma fonte só).
INDICES = store_firestore.INDICES + registro_firestore.INDICES


class ErroDoGcloud(RuntimeError):
    pass


@dataclass(frozen=True)
class Contexto:
    projeto: str
    regiao: str
    faturamento: str
    orcamento: str
    dono: str  # a conta do gcloud (e-mail): só em memória, para o papel no `cli@`
    # Os passos já prontos: um passo composto só lê o que existe quando as APIs estão ligadas
    # (sem elas, a leitura responde SERVICE_DISABLED).
    prontos: frozenset[str] = frozenset()

    def conta(self, nome: str) -> str:
        return f"{nome}@{self.projeto}.iam.gserviceaccount.com"


def _gcloud(ctx: Contexto, *args: str, cota: bool = False) -> list[str]:
    """O único jeito de montar um comando do `gcloud` aqui: sempre com o projeto do Viking."""
    comando = ["gcloud", *args, f"--project={ctx.projeto}", "--quiet"]
    if cota:  # APIs de faturamento pedem o projeto que paga a cota da chamada
        comando.append(f"--billing-project={ctx.projeto}")
    return comando


def _rodar(comando: list[str], *, entrada: str | None = None) -> subprocess.CompletedProcess:
    """`entrada` vai pela entrada padrão: é por ali que um segredo chega ao `gcloud`, nunca pelo
    argv (que aparece em `ps` e no histórico)."""
    if comando[0] != "gcloud" or not any(a.startswith("--project=") for a in comando):
        raise ErroDoGcloud(f"comando fora de _gcloud: {comando[:3]}")
    return subprocess.run(
        comando, input=entrada, capture_output=True, text=True, check=False, timeout=300
    )


# Como o gcloud diz "não existe" (cada comando do seu jeito; os textos são os medidos)
_NAO_EXISTE = (
    "NOT_FOUND",
    "not found",
    "does not exist",
    "may not exist",
    "was not found",
    "Cannot find service",  # `run services describe`, medido em 2026-09-30
)


def _ler(comando: list[str]) -> object | None:
    """JSON do comando, ou `None` se o recurso não existe. Qualquer outro erro sobe."""
    resultado = _rodar([*comando, "--format=json"])
    if resultado.returncode == 0:
        return json.loads(resultado.stdout or "null")
    if any(marca in resultado.stderr for marca in _NAO_EXISTE):
        return None
    raise ErroDoGcloud(resultado.stderr.strip().splitlines()[-1] if resultado.stderr else "?")


@dataclass(frozen=True)
class Estado:
    pronto: bool
    detalhe: str
    # Falso quando uma dependência não está pronta e o passo nem foi lido: os comandos de criação
    # saem marcados como "só se não existir" (o recurso pode já existir: na abertura da 10b, uma
    # API nova fez a listagem sugerir criar de novo o Firestore, as contas e o orçamento).
    medido: bool = True


@dataclass(frozen=True)
class Passo:
    nome: str
    descricao: str
    medir: Callable[[Contexto], Estado]
    comandos: Callable[[Contexto], list[list[str]]]
    depende: tuple[str, ...] = ()
    irreversivel: str = ""


# --- os passos, na ordem em que dependem um do outro ------------------------------------------


def _m_projeto(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "projects", "describe", ctx.projeto))
    if not isinstance(dados, dict):
        return Estado(False, "não existe (ou é de outra conta)")
    return Estado(dados.get("lifecycleState") == "ACTIVE", str(dados.get("lifecycleState")))


def _c_projeto(ctx: Contexto) -> list[list[str]]:
    return [_gcloud(ctx, "projects", "create", ctx.projeto, "--name=Viking")]


def _m_faturamento(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "billing", "projects", "describe", ctx.projeto))
    if not isinstance(dados, dict) or not dados.get("billingEnabled"):
        return Estado(False, "sem faturamento")
    ligado = str(dados.get("billingAccountName", "")).rsplit("/", 1)[-1]
    if ligado != ctx.faturamento:
        return Estado(False, f"ligado a outra conta (…{ligado[-6:]})")
    return Estado(True, f"conta …{ligado[-6:]}")


def _c_faturamento(ctx: Contexto) -> list[list[str]]:
    return [
        _gcloud(
            ctx,
            "billing",
            "projects",
            "link",
            ctx.projeto,
            f"--billing-account={ctx.faturamento}",
        )
    ]


def _m_apis(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "services", "list", "--enabled"))
    ligadas = {s["config"]["name"] for s in dados or []}
    faltam = [a for a in APIS if a not in ligadas]
    return Estado(not faltam, "todas" if not faltam else "faltam: " + ", ".join(faltam))


def _c_apis(ctx: Contexto) -> list[list[str]]:
    return [_gcloud(ctx, "services", "enable", *APIS)]


def _m_orcamento(ctx: Contexto) -> Estado:
    dados = _ler(
        _gcloud(
            ctx, "billing", "budgets", "list", f"--billing-account={ctx.faturamento}", cota=True
        )
    )
    meus = [b for b in dados or [] if b.get("displayName") == ORCAMENTO_NOME]
    if not meus:
        return Estado(False, "não existe")
    (orcamento,) = meus
    valor = orcamento.get("amount", {}).get("specifiedAmount", {})
    limites = sorted(r.get("thresholdPercent") for r in orcamento.get("thresholdRules", []))
    texto = f"{valor.get('units')} {valor.get('currencyCode')}, alertas {limites}"
    esperado = ctx.orcamento == f"{valor.get('units')}{valor.get('currencyCode')}"
    return Estado(esperado and limites == list(ALERTAS), texto)


def _c_orcamento(ctx: Contexto) -> list[list[str]]:
    return [
        _gcloud(
            ctx,
            "billing",
            "budgets",
            "create",
            f"--billing-account={ctx.faturamento}",
            f"--display-name={ORCAMENTO_NOME}",
            f"--budget-amount={ctx.orcamento}",
            *(f"--threshold-rule=percent={p}" for p in ALERTAS),
            f"--filter-projects=projects/{ctx.projeto}",
            cota=True,
        )
    ]


def _m_firestore(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "firestore", "databases", "describe", "--database=(default)"))
    if not isinstance(dados, dict):
        return Estado(False, "não existe")
    certo = (
        dados.get("locationId") == ctx.regiao
        and dados.get("type") == "FIRESTORE_NATIVE"
        and dados.get("deleteProtectionState") == "DELETE_PROTECTION_ENABLED"
    )
    return Estado(certo, f"{dados.get('locationId')}, {dados.get('type')}")


def _c_firestore(ctx: Contexto) -> list[list[str]]:
    return [
        _gcloud(
            ctx,
            "firestore",
            "databases",
            "create",
            "--database=(default)",
            f"--location={ctx.regiao}",
            "--type=firestore-native",
            "--edition=standard",
            "--delete-protection",
        )
    ]


def _politica_de_limpeza() -> str:
    """Guarda as últimas imagens e apaga o resto: 0,5 GB do registro são grátis."""
    politica = [
        {
            "name": "guardar-as-ultimas",
            "action": {"type": "Keep"},
            "mostRecentVersions": {"keepCount": GUARDAR_IMAGENS},
        },
        {"name": "apagar-o-resto", "action": {"type": "Delete"}, "condition": {"tagState": "any"}},
    ]
    arquivo = Path(tempfile.gettempdir()) / "viking-limpeza-do-registro.json"
    arquivo.write_text(json.dumps(politica))
    return str(arquivo)


def _m_registro(ctx: Contexto) -> Estado:
    dados = _ler(
        _gcloud(
            ctx, "artifacts", "repositories", "describe", REPOSITORIO, f"--location={ctx.regiao}"
        )
    )
    if not isinstance(dados, dict):
        return Estado(False, "não existe")
    politicas = sorted(dados.get("cleanupPolicies", {}))
    certo = politicas == ["apagar-o-resto", "guardar-as-ultimas"]
    return Estado(certo, f"docker, limpeza: {politicas or 'nenhuma'}")


def _c_registro(ctx: Contexto) -> list[list[str]]:
    """Só o que falta: o passo pode ser repetido depois de uma falha no meio."""
    existe = "apis" in ctx.prontos and _ler(
        _gcloud(
            ctx, "artifacts", "repositories", "describe", REPOSITORIO, f"--location={ctx.regiao}"
        )
    )
    criar = [
        _gcloud(
            ctx,
            "artifacts",
            "repositories",
            "create",
            REPOSITORIO,
            "--repository-format=docker",
            f"--location={ctx.regiao}",
        )
    ]
    return [
        *([] if existe else criar),
        _gcloud(
            ctx,
            "artifacts",
            "repositories",
            "set-cleanup-policies",
            REPOSITORIO,
            f"--location={ctx.regiao}",
            f"--policy={_politica_de_limpeza()}",
            "--no-dry-run",
        ),
    ]


def _membros(politica: object, papel: str) -> set[str]:
    if not isinstance(politica, dict):
        return set()
    return {m for b in politica.get("bindings", []) if b["role"] == papel for m in b["members"]}


def _m_contas(ctx: Contexto) -> Estado:
    faltam = []
    for nome in (MOTOR, *DO_DONO):
        if _ler(_gcloud(ctx, "iam", "service-accounts", "describe", ctx.conta(nome))) is None:
            faltam.append(f"{nome}@")
    if faltam:
        return Estado(False, "faltam: " + ", ".join(faltam))
    projeto = _ler(_gcloud(ctx, "projects", "get-iam-policy", ctx.projeto))
    if f"serviceAccount:{ctx.conta(MOTOR)}" not in _membros(projeto, "roles/datastore.user"):
        return Estado(False, "motor@ sem roles/datastore.user")
    for nome in DO_DONO:
        conta = _ler(_gcloud(ctx, "iam", "service-accounts", "get-iam-policy", ctx.conta(nome)))
        if f"user:{ctx.dono}" not in _membros(conta, "roles/iam.serviceAccountTokenCreator"):
            return Estado(False, f"o dono ainda não pode pedir token do {nome}@")
    return Estado(True, "motor@ (Firestore), cli@ e maos@ (o dono pede o token)")


def _c_contas(ctx: Contexto) -> list[list[str]]:
    """Só cria a conta que falta (repetir o passo não esbarra no "já existe"); os papéis são
    idempotentes no próprio IAM."""
    nomes = {
        MOTOR: "Viking: identidade do motor",
        CLI: "Viking: o terminal do dono",
        MAOS: "Viking: as mãos (o navegador do Mac)",
    }
    criar = [
        _gcloud(ctx, "iam", "service-accounts", "create", nome, f"--display-name={titulo}")
        for nome, titulo in nomes.items()
        if "apis" not in ctx.prontos
        or _ler(_gcloud(ctx, "iam", "service-accounts", "describe", ctx.conta(nome))) is None
    ]
    return [
        *criar,
        _gcloud(
            ctx,
            "projects",
            "add-iam-policy-binding",
            ctx.projeto,
            f"--member=serviceAccount:{ctx.conta(MOTOR)}",
            "--role=roles/datastore.user",
            "--condition=None",
        ),
        *(
            _gcloud(
                ctx,
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                ctx.conta(nome),
                f"--member=user:{ctx.dono}",
                "--role=roles/iam.serviceAccountTokenCreator",
            )
            for nome in DO_DONO
        ),
    ]


def _campos_do_indice(indice: dict) -> tuple[tuple[str, str], ...]:
    return tuple(
        (c["fieldPath"], c.get("order", ""))
        for c in indice.get("fields", [])
        if c["fieldPath"] != "__name__"
    )


def _indices(ctx: Contexto) -> dict[tuple[str, tuple[tuple[str, str], ...]], str]:
    """Os índices compostos que existem, com o estado (READY, CREATING...)."""
    dados = _ler(_gcloud(ctx, "firestore", "indexes", "composite", "list", "--database=(default)"))
    return {
        (i.get("name", "").split("/collectionGroups/")[-1].split("/")[0], _campos_do_indice(i)): (
            i.get("state", "")
        )
        for i in dados or []
    }


def _m_indices(ctx: Contexto) -> Estado:
    existentes = _indices(ctx)
    faltam = [f"{c}: {campos}" for c, campos in INDICES if existentes.get((c, campos)) != "READY"]
    return Estado(
        not faltam, "prontos" if not faltam else "faltam (ou construindo): " + "; ".join(faltam)
    )


def _c_indices(ctx: Contexto) -> list[list[str]]:
    existentes = _indices(ctx) if "firestore" in ctx.prontos else {}
    return [
        _gcloud(
            ctx,
            "firestore",
            "indexes",
            "composite",
            "create",
            "--database=(default)",
            f"--collection-group={colecao}",
            "--async",  # construir leva minutos (medido: passou de 300 s); a medida diz quando fica pronto
            *(
                f"--field-config=field-path={campo},order={ordem.lower()}"
                for campo, ordem in campos
            ),
        )
        for colecao, campos in INDICES
        # Só o que não existe: criar de novo um índice que existe (mesmo construindo) é
        # ALREADY_EXISTS, e o passo pararia antes do índice novo (medido na 10b, 2026-09-30).
        if "firestore" not in ctx.prontos or (colecao, campos) not in existentes
    ]


@dataclass(frozen=True)
class Segredo:
    nome: str  # no Secret Manager
    caminho: str  # o arquivo no volume do motor
    variavel: str  # a variável que diz ao `config` onde está o arquivo
    # O valor sobe do Mac, e só quando o dono decide (o do Gmail, depois da prova: D57, D60):
    # vazio não reprova o passo, e o deploy publica **sem** ele (Sessão 11, D61: o Gmail é
    # opcional na nuvem; um volume de segredo vazio derrubaria a revisão). Um segredo que não é
    # do Mac vazio continua impedindo o deploy.
    do_mac: bool = False


# Os segredos do motor (Sessões 10b e 10c, D59/D60): entregues como arquivo de um volume, nunca
# como variável de ambiente (o Google manda fixar a versão nesse caso, e o valor ficaria no
# ambiente do processo). Um diretório por segredo: o Cloud Run monta cada um no seu.
SEGREDOS = (
    Segredo("viking-gemini", "/segredos/gemini/chave", "VIKING_GEMINI_CHAVE_ARQUIVO"),
    Segredo("viking-agenda", "/segredos/agenda/token.json", "VIKING_AGENDA_TOKEN_ARQUIVO"),
    Segredo(
        "viking-gmail", "/segredos/gmail/token.json", "VIKING_GMAIL_TOKEN_ARQUIVO", do_mac=True
    ),
)
LER_SEGREDO = "roles/secretmanager.secretAccessor"


def _versoes(ctx: Contexto, nome: str) -> int:
    dados = _ler(_gcloud(ctx, "secrets", "versions", "list", nome, "--filter=state:ENABLED"))
    return len(dados or [])


def _m_segredos(ctx: Contexto) -> Estado:
    detalhes, pronto = [], True
    for segredo in SEGREDOS:
        if _ler(_gcloud(ctx, "secrets", "describe", segredo.nome)) is None:
            detalhes.append(f"{segredo.nome}: não existe")
            pronto = False
            continue
        politica = _ler(_gcloud(ctx, "secrets", "get-iam-policy", segredo.nome))
        if f"serviceAccount:{ctx.conta(MOTOR)}" not in _membros(politica, LER_SEGREDO):
            detalhes.append(f"{segredo.nome}: o motor@ não lê")
            pronto = False
            continue
        versoes = _versoes(ctx, segredo.nome)
        if not versoes and segredo.do_mac:
            detalhes.append(
                f"{segredo.nome}: vazio (sobe do Mac: `python scripts/nuvem.py segredo "
                f"{segredo.nome} --executar`)"
            )
        elif not versoes:
            detalhes.append(
                f"{segredo.nome}: vazio (suba com `python scripts/nuvem.py segredo "
                f"{segredo.nome} --executar`)"
            )
            pronto = False
        else:
            detalhes.append(f"{segredo.nome}: {versoes} versão(ões)")
    return Estado(pronto, "; ".join(detalhes))


def _c_segredos(ctx: Contexto) -> list[list[str]]:
    """Cria o segredo vazio (o valor sobe por `segredo`, pela entrada padrão) e dá ao `motor@` a
    leitura **só nele**, não no projeto."""
    criar = [
        _gcloud(
            ctx,
            "secrets",
            "create",
            s.nome,
            "--replication-policy=automatic",
            "--labels=app=viking",
        )
        for s in SEGREDOS
        if "apis" not in ctx.prontos or _ler(_gcloud(ctx, "secrets", "describe", s.nome)) is None
    ]
    ler = [
        _gcloud(
            ctx,
            "secrets",
            "add-iam-policy-binding",
            s.nome,
            f"--member=serviceAccount:{ctx.conta(MOTOR)}",
            f"--role={LER_SEGREDO}",
        )
        for s in SEGREDOS
    ]
    return [*criar, *ler]


# (coleção, campo) que a TTL apaga: o registro de ações e as confirmações vivem 30 dias na nuvem
# (Sessões 10b e 10c; a das confirmações passa das janelas que ainda as leem, 8 e 7 dias); as
# tarefas das mãos, 1 dia (Sessão 11: o turno já as apaga; isto leva o que sobrar).
TTLS = (("acoes", "expira_em"), ("confirmacoes", "apagar_em"), ("tarefas", "apagar_em"))


def _estados_ttl(ctx: Contexto) -> dict[tuple[str, str], str]:
    dados = _ler(_gcloud(ctx, "firestore", "fields", "ttls", "list", "--database=(default)"))
    estados: dict[tuple[str, str], str] = {}
    for item in dados or []:
        for colecao, campo in TTLS:
            if item.get("name", "").endswith(f"/collectionGroups/{colecao}/fields/{campo}"):
                estados[(colecao, campo)] = (item.get("ttlConfig") or {}).get("state", "") or "?"
    return estados


def _m_ttl(ctx: Contexto) -> Estado:
    estados = _estados_ttl(ctx)
    detalhes = [f"{c}.{f}: {estados.get((c, f), 'desligada')}" for c, f in TTLS]
    return Estado(all(estados.get(t) == "ACTIVE" for t in TTLS), "; ".join(detalhes))


def _c_ttl(ctx: Contexto) -> list[list[str]]:
    """Só as que faltam (ligar de novo uma que está ligada é um pedido à toa)."""
    estados = _estados_ttl(ctx) if "firestore" in ctx.prontos else {}
    return [
        _gcloud(
            ctx,
            "firestore",
            "fields",
            "ttls",
            "update",
            campo,
            f"--collection-group={colecao}",
            "--database=(default)",
            "--enable-ttl",
            "--async",  # ligar leva minutos; a medida diz quando fica ACTIVE
        )
        for colecao, campo in TTLS
        if estados.get((colecao, campo)) not in ("ACTIVE", "CREATING")
    ]


# --- o envio de lembretes pela nuvem (Sessão 11, D61): roda depois do portão da 10c ------------

API_DO_AGENDADOR = "cloudscheduler.googleapis.com"
TAREFA_DO_AGENDADOR = "viking-lembretes"
# A rodada tem 200 s de prazo (`reminders/agendador.PRAZO_DA_RODADA_S`); o Scheduler espera um
# pouco mais e não repete: a próxima rodada vem no minuto seguinte.
ESPERA_DA_RODADA = "250s"


def _tarefa_certa(ctx: Contexto, tarefa: dict) -> list[str]:
    """O que difere do esperado na tarefa do Scheduler (vazio = certa)."""
    url = _url(ctx)
    alvo = tarefa.get("httpTarget", {})
    oidc = alvo.get("oidcToken", {})
    esperado = {
        "a cada minuto": tarefa.get("schedule") == "* * * * *",
        "ligada": tarefa.get("state") == "ENABLED",
        "POST na rota do envio": alvo.get("uri") == f"{url}/tarefas/lembretes"
        and alvo.get("httpMethod") == "POST",
        "como o agendador@": oidc.get("serviceAccountEmail") == ctx.conta(AGENDADOR),
        "com a audience do motor": oidc.get("audience") == url,
    }
    return [nome for nome, certo in esperado.items() if not certo]


def _m_agendador(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "services", "list", "--enabled"))
    if API_DO_AGENDADOR not in {s["config"]["name"] for s in dados or []}:
        return Estado(False, "a API do Cloud Scheduler desligada (liga depois do portão da 10c)")
    if _ler(_gcloud(ctx, "iam", "service-accounts", "describe", ctx.conta(AGENDADOR))) is None:
        return Estado(False, "falta o agendador@")
    politica = _ler(
        _gcloud(ctx, "run", "services", "get-iam-policy", SERVICO, f"--region={ctx.regiao}")
    )
    if f"serviceAccount:{ctx.conta(AGENDADOR)}" not in _membros(politica, "roles/run.invoker"):
        return Estado(False, "o agendador@ ainda não invoca o motor")
    tarefa = _ler(
        _gcloud(
            ctx, "scheduler", "jobs", "describe", TAREFA_DO_AGENDADOR, f"--location={ctx.regiao}"
        )
    )
    if not isinstance(tarefa, dict):
        return Estado(False, "falta a tarefa do Scheduler")
    errado = _tarefa_certa(ctx, tarefa)
    if errado:
        return Estado(False, "a tarefa existe, mas não está: " + ", ".join(errado))
    return Estado(True, "a cada minuto, como agendador@, só na rota do envio")


def _c_agendador(ctx: Contexto) -> list[list[str]]:
    """Liga a API, cria o agendador@ (se falta), dá a ele o `run.invoker` no motor e cria a
    tarefa (se falta). O token é OIDC, com a audience do motor: nenhuma chave em disco (D47)."""
    pronta = "apis" in ctx.prontos
    criar_conta = (
        not pronta
        or _ler(_gcloud(ctx, "iam", "service-accounts", "describe", ctx.conta(AGENDADOR))) is None
    )
    # A URL sai do número do projeto; antes das APIs (na listagem de um projeto que ainda não
    # existe), um marcador, sem ler nada.
    url = _url(ctx) if pronta else f"https://{SERVICO}-<número do projeto>.{ctx.regiao}.run.app"
    comandos = [_gcloud(ctx, "services", "enable", API_DO_AGENDADOR)]
    if criar_conta:
        comandos.append(
            _gcloud(
                ctx,
                "iam",
                "service-accounts",
                "create",
                AGENDADOR,
                "--display-name=Viking: o agendador do envio de lembretes",
            )
        )
    comandos.append(
        _gcloud(
            ctx,
            "run",
            "services",
            "add-iam-policy-binding",
            SERVICO,
            f"--region={ctx.regiao}",
            f"--member=serviceAccount:{ctx.conta(AGENDADOR)}",
            "--role=roles/run.invoker",
        )
    )
    comandos.append(
        _gcloud(
            ctx,
            "scheduler",
            "jobs",
            "create",
            "http",
            TAREFA_DO_AGENDADOR,
            f"--location={ctx.regiao}",
            "--schedule=* * * * *",
            "--time-zone=Etc/UTC",
            f"--uri={url}/tarefas/lembretes",
            "--http-method=POST",
            f"--oidc-service-account-email={ctx.conta(AGENDADOR)}",
            f"--oidc-token-audience={url}",
            f"--attempt-deadline={ESPERA_DA_RODADA}",
            "--max-retry-attempts=0",
            "--description=Viking: envia por e-mail os lembretes vencidos",
        )
    )
    return comandos


PASSOS = (
    Passo("projeto", "o projeto só do Viking", _m_projeto, _c_projeto),
    Passo(
        "faturamento",
        "o faturamento do dono ligado",
        _m_faturamento,
        _c_faturamento,
        depende=("projeto",),
    ),
    Passo("apis", "as APIs que o Viking usa", _m_apis, _c_apis, depende=("faturamento",)),
    Passo("orcamento", "orçamento com alertas (só avisa)", _m_orcamento, _c_orcamento, ("apis",)),
    Passo(
        "firestore",
        "o banco (default), nativo",
        _m_firestore,
        _c_firestore,
        depende=("apis",),
        irreversivel="o local do Firestore não muda depois de criado",
    ),
    Passo("registro", "Artifact Registry das imagens", _m_registro, _c_registro, ("apis",)),
    Passo("contas", "contas de serviço e papéis", _m_contas, _c_contas, ("apis",)),
    Passo("indices", "índices compostos do Firestore", _m_indices, _c_indices, ("firestore",)),
    Passo(
        "segredos",
        "a chave do Gemini e os tokens da agenda e do Gmail (só o motor@ lê)",
        _m_segredos,
        _c_segredos,
        depende=("apis", "contas"),
    ),
    Passo(
        "ttl",
        "o registro de ações e as confirmações apagam sozinhos depois de 30 dias, as tarefas das "
        "mãos depois de 1",
        _m_ttl,
        _c_ttl,
        depende=("firestore",),
        irreversivel=(
            "apaga o registro de ações (a regra do dono) e as confirmações (D60) com mais de "
            "30 dias, e as tarefas das mãos (D61) com mais de 1"
        ),
    ),
    Passo(
        "agendador",
        "o envio de lembretes por e-mail a cada minuto, com o Mac desligado (depois do portão "
        "da 10c)",
        _m_agendador,
        _c_agendador,
        depende=("contas",),
        irreversivel=(
            "o motor passa a enviar sozinho, a cada minuto, o e-mail dos lembretes vencidos, só "
            "para a conta do dono e no limite de 20 em 24 h; custa de US$ 0 a 0,10 por mês"
        ),
    ),
)


# --- o deploy do motor (Sessão 10, C6) ---------------------------------------------------------

SERVICO = "motor"
RAIZ = config.REPO_ROOT
ESPERA_DO_IAM_S = 180
_LOCAIS = ("git", "docker", "gh")


def _local(comando: list[str], *, entrada: str | None = None) -> subprocess.CompletedProcess:
    """`git`, `docker` e `gh`: o que o deploy lê ou usa fora do GCP. O `gcloud` nunca passa aqui
    (só por `_rodar`, com o projeto)."""
    if comando[0] not in _LOCAIS:
        raise ErroDoGcloud(f"comando local não previsto: {comando[0]}")
    return subprocess.run(
        comando, input=entrada, capture_output=True, text=True, check=False, timeout=1800, cwd=RAIZ
    )


def _saida(comando: list[str]) -> str:
    resultado = _local(comando)
    if resultado.returncode != 0:
        raise ErroDoGcloud(f"{' '.join(comando[:3])}: {resultado.stderr.strip()[-300:]}")
    return resultado.stdout.strip()


def caminhos_da_imagem() -> list[str]:
    """O que muda a imagem, derivado do próprio `Dockerfile` (skill `nuvem-e-deploy` §6): as
    origens de cada `COPY` que não vem de outro estágio, mais o `Dockerfile` e o `.dockerignore`."""
    caminhos = ["Dockerfile", ".dockerignore"]
    for linha in (RAIZ / "Dockerfile").read_text().splitlines():
        if linha.startswith("COPY ") and "--from=" not in linha:
            caminhos += linha.split()[1:-1]
    return caminhos


@dataclass(frozen=True)
class Situacao:
    head: str
    limpo: bool
    publicado: bool
    ci: str
    no_ar: str | None  # o SHA da imagem no ar (a tag), ou None sem serviço
    mudou_desde: int | None  # commits nos caminhos da imagem desde a do ar
    volumes_no_ar: frozenset[str] = frozenset()  # os segredos montados na revisão no ar


def _volumes(servico: dict) -> frozenset[str]:
    modelo = servico["spec"]["template"]["spec"]
    return frozenset(
        nome
        for v in modelo.get("volumes", [])
        if (nome := (v.get("secret") or {}).get("secretName"))
    )


def situacao(ctx: Contexto) -> Situacao:
    head = _saida(["git", "rev-parse", "HEAD"])
    remoto = _saida(["git", "ls-remote", "origin", "refs/heads/master"]).split()[:1]
    ci = _saida(
        [
            "gh",
            "run",
            "list",
            "--commit",
            head,
            "--workflow",
            "testes",
            "--json",
            "status,conclusion",
            "--jq",
            '.[0] | "\\(.status) \\(.conclusion)"',
        ]
    )
    servico = _ler(_gcloud(ctx, "run", "services", "describe", SERVICO, f"--region={ctx.regiao}"))
    no_ar = mudou = None
    volumes: frozenset[str] = frozenset()
    if isinstance(servico, dict):
        volumes = _volumes(servico)
        imagem = servico["spec"]["template"]["spec"]["containers"][0]["image"]
        no_ar = imagem.rsplit(":", 1)[-1]
        mudou = int(
            _saida(["git", "rev-list", "--count", f"{no_ar}..{head}", "--", *caminhos_da_imagem()])
        )
    return Situacao(
        head=head,
        limpo=_saida(["git", "status", "--porcelain"]) == "",
        publicado=remoto == [head],
        ci=ci,
        no_ar=no_ar,
        mudou_desde=mudou,
        volumes_no_ar=volumes,
    )


def _imagem(ctx: Contexto, sha: str) -> str:
    return f"{ctx.regiao}-docker.pkg.dev/{ctx.projeto}/{REPOSITORIO}/{SERVICO}:{sha}"


def _url(ctx: Contexto) -> str:
    """A URL do serviço, que o Cloud Run monta com o número do projeto: é a audience que o motor
    exige, e sai antes do primeiro deploy."""
    dados = _ler(_gcloud(ctx, "projects", "describe", ctx.projeto))
    assert isinstance(dados, dict)
    return f"https://{SERVICO}-{dados['projectNumber']}.{ctx.regiao}.run.app"


def _fuso() -> str:
    fuso = os.getenv("VIKING_NUVEM_FUSO", "")
    if not fuso:
        raise SystemExit(
            "nuvem.py: falta VIKING_NUVEM_FUSO no .env (o fuso do dono; a nuvem roda em UTC)"
        )
    return fuso


def montaveis(ctx: Contexto) -> tuple[tuple[Segredo, ...], list[str]]:
    """(os segredos que vão ao deploy, os que faltam e impedem o deploy). Vai o que tem versão; um
    `do_mac` vazio fica de fora (o motor sem ele não tem as tools dele: `config.gmail_no_motor`),
    e qualquer outro vazio impede."""
    montados = tuple(s for s in SEGREDOS if _versoes(ctx, s.nome))
    faltam = [s.nome for s in SEGREDOS if not s.do_mac and s not in montados]
    return montados, faltam


def comandos_do_deploy(
    ctx: Contexto, sha: str, montados: tuple[Segredo, ...] = SEGREDOS
) -> list[list[str]]:
    return [
        _gcloud(
            ctx,
            "run",
            "deploy",
            SERVICO,
            f"--image={_imagem(ctx, sha)}",
            f"--region={ctx.regiao}",
            f"--service-account={ctx.conta(MOTOR)}",
            "--no-allow-unauthenticated",
            "--min-instances=0",
            "--max-instances=2",
            "--concurrency=10",
            "--cpu=1",
            "--memory=512Mi",
            # 300 s: um turno medido levou até 3 s (2026-09-30), e as esperas de cota do Gmail
            # (10c) somam até 126 s; só é cobrado enquanto o pedido roda.
            "--timeout=300",
            "--labels=app=viking",
            # Os segredos com versão, como volumes, e nenhum outro (o `--set-secrets` troca a
            # lista; o que fica de fora sai da revisão nova).
            "--set-secrets=" + ",".join(f"{s.caminho}={s.nome}:latest" for s in montados),
            "--set-env-vars="
            + ",".join(
                [
                    f"VIKING_NUVEM_PROJETO={ctx.projeto}",
                    f"VIKING_NUVEM_URL={_url(ctx)}",
                    f"VIKING_TIMEZONE={_fuso()}",
                    *(f"{s.variavel}={s.caminho}" for s in montados),
                ]
            ),
        ),
        # O terminal e as mãos invocam (cada um só com as rotas dele: `motor.QUEM_FALA`); o
        # agendador@ ganha o dele no passo `agendador`.
        *(
            _gcloud(
                ctx,
                "run",
                "services",
                "add-iam-policy-binding",
                SERVICO,
                f"--region={ctx.regiao}",
                f"--member=serviceAccount:{ctx.conta(nome)}",
                "--role=roles/run.invoker",
            )
            for nome in DO_DONO
        ),
    ]


def _token(ctx: Contexto, *args: str) -> str:
    """Um token do gcloud, que nunca é impresso nem gravado: vai para o `docker login` pela entrada
    padrão ou para o cabeçalho de um pedido."""
    resultado = _rodar(_gcloud(ctx, "auth", *args))
    if resultado.returncode != 0 or not resultado.stdout.strip():
        raise ErroDoGcloud(f"auth {args[0]}: {resultado.stderr.strip()[-200:]}")
    return resultado.stdout.strip()


def publicar(ctx: Contexto, sha: str, montados: tuple[Segredo, ...]) -> None:
    """Constrói, envia e põe no ar. Só roda depois de `situacao` dizer que dá (árvore limpa, HEAD
    no GitHub, CI verde) e do ok do dono."""
    imagem = _imagem(ctx, sha)
    print(f"$ docker build (VIKING_COMMIT={sha[:12]}) → {imagem}")
    _saida(["docker", "build", "--build-arg", f"VIKING_COMMIT={sha}", "-t", imagem, "."])
    registro = f"https://{ctx.regiao}-docker.pkg.dev"
    login = _local(
        ["docker", "login", "-u", "oauth2accesstoken", "--password-stdin", registro],
        entrada=_token(ctx, "print-access-token"),
    )
    if login.returncode != 0:
        raise ErroDoGcloud(f"docker login: {login.stderr.strip()[-200:]}")
    try:
        print(f"$ docker push {imagem}")
        _saida(["docker", "push", imagem])
    finally:
        _local(["docker", "logout", registro])  # o token de 1 h não fica no ~/.docker
    for comando in comandos_do_deploy(ctx, sha, montados):
        print(f"$ {_legivel(comando)}")
        resultado = _rodar(comando)
        if resultado.returncode != 0:
            raise ErroDoGcloud(resultado.stderr.strip()[-400:])


@dataclass(frozen=True)
class Prova:
    nome: str
    passou: bool
    detalhe: str


def _segredos_so_como_volume(
    servico: dict, montados: tuple[Segredo, ...] = SEGREDOS
) -> tuple[bool, str]:
    """No `describe` do serviço: as variáveis são só as esperadas para os segredos montados
    (nenhuma com `valueFrom`, que seria um segredo no ambiente), e os volumes de segredo são
    exatamente os montados."""
    modelo = servico["spec"]["template"]["spec"]
    variaveis = {v.get("name"): v for v in modelo["containers"][0].get("env", [])}
    esperadas = {"VIKING_NUVEM_PROJETO", "VIKING_NUVEM_URL", "VIKING_TIMEZONE"} | {
        s.variavel for s in montados
    }
    sem_segredo = set(variaveis) <= esperadas and not any(
        "valueFrom" in v for v in variaveis.values()
    )
    volumes = _volumes(servico)
    certos = volumes == {s.nome for s in montados}
    return sem_segredo and certos, f"variáveis {sorted(variaveis)}; volumes {sorted(volumes)}"


def _invocadores_certos(ctx: Contexto, quem: set[str]) -> bool:
    """O terminal e as mãos sempre; o agendador@ depois do passo `agendador`; ninguém mais (nem
    `allUsers`, nem o dono em pessoa, nem o motor@)."""
    precisam = {f"serviceAccount:{ctx.conta(nome)}" for nome in DO_DONO}
    podem = precisam | {f"serviceAccount:{ctx.conta(AGENDADOR)}"}
    return precisam <= quem <= podem


def provas(ctx: Contexto, sha: str, montados: tuple[Segredo, ...] = SEGREDOS) -> list[Prova]:
    """Rodam sempre, com ou sem deploy (skill `nuvem-e-deploy` §6 e §8): a imagem no ar, o IAM do
    serviço, a recusa sem token, a recusa do nosso código, o caminho com a identidade certa, a
    consulta que pede o índice, e os erros no log."""
    import requests

    resultado: list[Prova] = []
    servico = _ler(_gcloud(ctx, "run", "services", "describe", SERVICO, f"--region={ctx.regiao}"))
    if not isinstance(servico, dict):
        return [Prova("serviço no ar", False, "não existe")]
    imagem = servico["spec"]["template"]["spec"]["containers"][0]["image"]
    no_ar = imagem.rsplit("/", 1)[-1]
    resultado.append(Prova("imagem no ar = a esperada", imagem == _imagem(ctx, sha), no_ar))
    certo, detalhe = _segredos_so_como_volume(servico, montados)
    resultado.append(Prova("segredos só como volume, nada no ambiente", certo, detalhe))
    # O `status.url` é a URL antiga, com hash; a determinística (com o número do projeto) é a
    # audience que o motor exige, e o Cloud Run a lista nesta anotação (medido em 2026-09-30).
    anotacoes = servico["metadata"].get("annotations", {})
    urls = json.loads(anotacoes.get("run.googleapis.com/urls", "[]"))
    url = _url(ctx)
    resultado.append(Prova("URL = a audience", url in urls, url))

    politica = _ler(
        _gcloud(ctx, "run", "services", "get-iam-policy", SERVICO, f"--region={ctx.regiao}")
    )
    quem = _membros(politica, "roles/run.invoker")
    resultado.append(
        Prova(
            "só o viking-cli@, o viking-maos@ (e o viking-agendador@) invocam",
            _invocadores_certos(ctx, quem),
            ", ".join(sorted(quem)) or "ninguém",
        )
    )

    sem = requests.get(f"{url}/versao", timeout=30)
    nosso = sem.text.strip() in ("sem token", "token recusado", "identidade sem acesso")
    resultado.append(
        Prova(
            "sem token: recusado pelo Google",
            sem.status_code == 403 and not nosso,
            f"HTTP {sem.status_code}",
        )
    )
    dono = requests.get(
        f"{url}/versao",
        headers={"Authorization": f"Bearer {_token(ctx, 'print-identity-token')}"},
        timeout=30,
    )
    resultado.append(
        Prova(
            "o dono em pessoa: recusado pelo motor",
            dono.status_code in (401, 403)
            and dono.text.strip() in ("token recusado", "identidade sem acesso"),
            f"HTTP {dono.status_code} {dono.text.strip()[:40]!r}",
        )
    )
    cli = _token(
        ctx,
        "print-identity-token",
        f"--impersonate-service-account={ctx.conta(CLI)}",
        f"--audiences={url}",
        "--include-email",
    )
    cabecalho = {"Authorization": f"Bearer {cli}"}
    # A permissão de invocar recém-dada leva um tempo para valer (medido em 2026-09-30: <1 min).
    # Espera só enquanto o 403 é a página do Google; um 403 do nosso código não é propagação.
    esperou = 0
    while True:
        versao = requests.get(f"{url}/versao", headers=cabecalho, timeout=60)
        propagando = versao.status_code == 403 and versao.text.lstrip().startswith("<")
        if not propagando or esperou >= ESPERA_DO_IAM_S:
            break
        time.sleep(15)
        esperou += 15
    commit = versao.json().get("commit") if versao.status_code == 200 else None
    detalhe = f"HTTP {versao.status_code}" + (f", depois de {esperou} s" if esperou else "")
    resultado.append(Prova("viking-cli@: /versao = a imagem no ar", commit == sha, detalhe))
    for rota in ("/lembretes", "/fumaca/vencidos", "/fumaca/registro"):
        resposta = requests.get(f"{url}{rota}", headers=cabecalho, timeout=60)
        resultado.append(
            Prova(
                f"viking-cli@: {rota}", resposta.status_code == 200, f"HTTP {resposta.status_code}"
            )
        )

    segredos = requests.get(f"{url}/fumaca/segredos", headers=cabecalho, timeout=60)
    lidos = segredos.json() if segredos.status_code == 200 else {}
    com_gmail = any(s.nome == "viking-gmail" for s in montados)
    resultado.append(
        Prova(
            "viking-cli@: /fumaca/segredos (a chave lê, os tokens renovam; o do Gmail "
            f"{'montado' if com_gmail else 'ainda não subiu: sem ele'})",
            lidos == {"gemini": True, "agenda": True, "gmail": com_gmail},
            f"HTTP {segredos.status_code} {lidos}",
        )
    )
    no_ar = versao.json().get("gmail") if versao.status_code == 200 else None
    resultado.append(
        Prova("viking-cli@: /versao diz se tem o Gmail", no_ar is com_gmail, f"gmail: {no_ar}")
    )
    # O envio de lembretes só está ligado com o agendador pronto e o Gmail montado
    # (`reminders/agendador.ligado`); a primeira rodada vem até 1 min depois do passo.
    envio = versao.json().get("envio_de_lembretes") if versao.status_code == 200 else None
    esperado = com_gmail and _m_agendador(ctx).pronto
    resultado.append(
        Prova(
            "viking-cli@: /versao diz se o envio de lembretes está ligado",
            envio is esperado,
            f"envio_de_lembretes: {envio} (esperado {esperado})",
        )
    )
    resultado.extend(_provas_das_portas(ctx, url, cabecalho))

    filtro = (
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICO}" '
        "AND severity>=ERROR"
    )
    erros = _ler(_gcloud(ctx, "logging", "read", filtro, "--freshness=30m", "--limit=20"))
    resultado.append(Prova("log sem erro (30 min)", not erros, f"{len(erros or [])} erro(s)"))
    return resultado


def _provas_das_portas(ctx: Contexto, url: str, cabecalho_do_cli: dict) -> list[Prova]:
    """Cada conta só na porta dela (`motor.QUEM_FALA`, Sessão 11): o terminal não entra nas mãos,
    as mãos não leem o resto. O pedido das mãos é torto de propósito (`por` que não é hex): passa
    pela identidade e o motor responde 400, sem pegar nenhuma tarefa de verdade."""
    import requests

    recusa = ("identidade sem acesso",)
    maos = {
        "Authorization": "Bearer "
        + _token(
            ctx,
            "print-identity-token",
            f"--impersonate-service-account={ctx.conta(MAOS)}",
            f"--audiences={url}",
            "--include-email",
        )
    }
    pedidos = [
        ("viking-cli@: /maos/pegar recusado pelo motor", cabecalho_do_cli, "/maos/pegar", 403),
        ("viking-maos@: /versao recusado pelo motor", maos, "/versao", 403),
        (
            "viking-maos@: /maos/pegar entra (pedido torto: 400, nada pego)",
            maos,
            "/maos/pegar",
            400,
        ),
    ]
    provas_ = []
    for nome, cabecalho, rota, status in pedidos:
        if rota == "/versao":
            resposta = requests.get(f"{url}{rota}", headers=cabecalho, timeout=60)
        else:
            resposta = requests.post(
                f"{url}{rota}", headers=cabecalho, json={"por": "prova"}, timeout=60
            )
        certo = resposta.status_code == status and (
            status != 403 or resposta.text.strip() in recusa
        )
        provas_.append(Prova(nome, certo, f"HTTP {resposta.status_code}"))
    return provas_


def deploy(ctx: Contexto, executar: bool) -> int:
    agora = situacao(ctx)
    print(
        f"HEAD {agora.head[:12]} · árvore {'limpa' if agora.limpo else 'SUJA'} · "
        f"{'no GitHub' if agora.publicado else 'NÃO está no GitHub'} · CI: {agora.ci or '?'}"
    )
    if agora.no_ar is None:
        print("No ar: nada (o serviço ainda não existe).")
    else:
        print(
            f"No ar: {agora.no_ar[:12]} · commits desde ela nos caminhos da imagem "
            f"({', '.join(caminhos_da_imagem())}): {agora.mudou_desde}"
        )
    pode = agora.limpo and agora.publicado and agora.ci == "completed success"
    montados, faltam = montaveis(ctx)
    # Nada nos caminhos da imagem desde a que está no ar, e os mesmos segredos montados: ela já é
    # o código de agora, e publicar de novo só trocaria a etiqueta (skill `nuvem-e-deploy` §4, a
    # segunda pergunta). Um segredo que ganhou versão (o do Gmail, subido do Mac) pede revisão.
    em_dia = (
        agora.no_ar is not None
        and agora.mudou_desde == 0
        and agora.volumes_no_ar == {s.nome for s in montados}
    )
    esperado = agora.no_ar if em_dia and agora.no_ar else agora.head
    if executar:
        if not pode:
            print("Não publico: a imagem tem de ser um commit limpo, no GitHub e com CI verde.")
            return 1
        if em_dia:
            print("Nada mudou na imagem desde a que está no ar; só as provas.")
        else:
            if faltam:
                # Um volume de segredo sem versão derruba a revisão nova: nada é construído.
                print(f"Não publico: sem valor no Secret Manager: {', '.join(faltam)}.")
                return 1
            publicar(ctx, agora.head, montados)
    elif not em_dia:
        for comando in comandos_do_deploy(ctx, agora.head, montados):
            print(f"  → {_legivel(comando)}")
        print("Nada foi publicado (sem --executar).")
    fora = [s.nome for s in SEGREDOS if s not in montados]
    if fora:
        print(f"Fora desta revisão (sem versão; sobe do Mac): {', '.join(fora)}.")
    print("Provas (rodam sempre):")
    feitas = provas(ctx, esperado, montados)
    for prova in feitas:
        print(f"  {'✅' if prova.passou else '❌'} {prova.nome}: {prova.detalhe}")
    return 0 if all(p.passou for p in feitas) else 2


# --- a linha de comando ------------------------------------------------------------------------


# --- os valores dos segredos e o turno real no ar (Sessão 10b) ----------------------------------


def _chave_do_gemini() -> str:
    chave = (config.GEMINI_API_KEY or "").strip()
    if not chave:
        raise SystemExit("nuvem.py: o .env não tem GEMINI_API_KEY (nada foi enviado)")
    return chave


def _token_da_agenda() -> str:
    """O token da agenda deste computador, conferido antes de subir (sem mostrar nada dele)."""
    try:
        texto = config.GOOGLE_TOKEN_PATH.read_text()
        info = json.loads(texto)
    except (OSError, ValueError):
        raise SystemExit(
            "nuvem.py: o token da agenda não abriu como JSON (nada foi enviado)"
        ) from None
    escopos = info.get("scopes") or []
    if isinstance(escopos, str):
        escopos = escopos.split()
    if not info.get("refresh_token") or "https://www.googleapis.com/auth/calendar" not in escopos:
        raise SystemExit(
            "nuvem.py: o token da agenda não renova ou não tem a permissão da agenda (nada foi "
            "enviado)"
        )
    return texto


def _token_do_gmail() -> str:
    """O token do Gmail DESTE computador (o Mac: o VPS não guarda token do Gmail, D57), conferido
    antes de subir: JSON, renovável e com a permissão do Gmail. Nada dele é mostrado."""
    try:
        texto = config.GMAIL_TOKEN_PATH.read_text()
        info = json.loads(texto)
    except (OSError, ValueError):
        raise SystemExit(
            "nuvem.py: o token do Gmail não abriu como JSON; no Mac, `viking gmail --login` "
            "(nada foi enviado)"
        ) from None
    escopos = info.get("scopes") or []
    if isinstance(escopos, str):
        escopos = escopos.split()
    if (
        not info.get("refresh_token")
        or "https://www.googleapis.com/auth/gmail.modify" not in escopos
    ):
        raise SystemExit(
            "nuvem.py: o token do Gmail não renova ou não tem a permissão do Gmail (nada foi "
            "enviado)"
        )
    return texto


FONTES: dict[str, tuple[str, Callable[[], str]]] = {
    "viking-gemini": ("o GEMINI_API_KEY do .env", _chave_do_gemini),
    "viking-agenda": ("o token da agenda de secrets/", _token_da_agenda),
    "viking-gmail": ("o token do Gmail de secrets/ (no Mac)", _token_do_gmail),
}


def segredo(ctx: Contexto, nome: str, executar: bool) -> int:
    """Sem flag, mede; com `--executar`, sobe uma versão nova com o valor pela entrada padrão do
    `gcloud`. O valor nunca aparece no argv, na saída nem na conversa."""
    origem, ler = FONTES[nome]
    print(f"{nome}: {_versoes(ctx, nome)} versão(ões) habilitada(s); a fonte é {origem}.")
    if not executar:
        print("Nada foi enviado (sem --executar).")
        return 0
    valor = ler()
    resultado = _rodar(
        _gcloud(ctx, "secrets", "versions", "add", nome, "--data-file=-"), entrada=valor
    )
    if resultado.returncode != 0:
        linhas = resultado.stderr.strip().splitlines()
        print(f"❌ {nome}: {linhas[-1] if linhas else '?'}", file=sys.stderr)
        return 1
    print(f"✅ {nome}: versão nova enviada ({_versoes(ctx, nome)} habilitada(s)).")
    return 0


def prova_chat(ctx: Contexto, mensagem: str) -> int:
    """Um turno real do chat no ar, com o `viking-cli@`: gasta (poucos décimos de centavo), por
    isso só roda quando pedido. Mostra o tempo, o gasto e o começo da resposta."""
    import requests

    url = _url(ctx)
    token = _token(
        ctx,
        "print-identity-token",
        f"--impersonate-service-account={ctx.conta(CLI)}",
        f"--audiences={url}",
        "--include-email",
    )
    pedido = {"mensagem": mensagem, "historico": [], "nota": "", "sessao": "prova", "numero": 1}
    inicio = time.monotonic()
    resposta = requests.post(
        f"{url}/chat", json=pedido, headers={"Authorization": f"Bearer {token}"}, timeout=320
    )
    segundos = time.monotonic() - inicio
    dados = (
        resposta.json()
        if resposta.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    print(f"HTTP {resposta.status_code} em {segundos:.1f} s")
    print(f"consumo: {dados.get('consumo') or '-'} · gasto: {dados.get('gasto')}")
    texto = dados.get("resposta") or dados.get("erro") or ""
    print(f"resposta (começo): {str(texto)[:200]!r}")
    return 0 if resposta.status_code == 200 and dados.get("resposta") else 2


def _contexto(*, so_projeto: bool = False) -> Contexto:
    """`so_projeto`: o subcomando `segredo`, que roda também no Mac (o token do Gmail sobe de lá,
    D60), onde o `.env` só tem o projeto e a URL da nuvem."""
    exigidas = ("VIKING_NUVEM_PROJETO",) + (
        () if so_projeto else ("VIKING_NUVEM_FATURAMENTO", "VIKING_NUVEM_ORCAMENTO")
    )
    faltam = [nome for nome in exigidas if not os.getenv(nome)]
    if faltam:
        raise SystemExit("nuvem.py: faltam no .env: " + ", ".join(faltam))
    dono = subprocess.run(
        ["gcloud", "config", "get", "account"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if "@" not in dono:
        raise SystemExit("nuvem.py: o gcloud não tem conta ativa (gcloud auth list)")
    return Contexto(
        projeto=config.NUVEM_PROJETO,
        regiao=config.NUVEM_REGIAO,
        faturamento=os.getenv("VIKING_NUVEM_FATURAMENTO", ""),
        orcamento=os.getenv("VIKING_NUVEM_ORCAMENTO", ""),
        dono=dono,
    )


def _legivel(comando: list[str]) -> str:
    """O comando para o dono ler: sem as flags que todo comando leva, e a conta de faturamento só
    pelo fim (a saída vai para a conversa)."""
    partes = []
    for a in comando:
        if a == "--quiet" or a.startswith("--project="):
            continue
        if a.startswith("--billing-account="):
            a = "--billing-account=…" + a[-6:]
        partes.append(a)
    return " ".join(partes)


def medir(ctx: Contexto) -> list[tuple[Passo, Estado]]:
    """Cada passo, na ordem; um passo cuja dependência não está pronta não é medido (a leitura
    esbarraria no que falta: projeto inexistente, API desligada)."""
    medidos: list[tuple[Passo, Estado]] = []
    prontos: set[str] = set()
    for passo in PASSOS:
        faltam = [d for d in passo.depende if d not in prontos]
        estado = (
            Estado(False, f"depende de {', '.join(faltam)}", medido=False)
            if faltam
            else passo.medir(ctx)
        )
        if estado.pronto:
            prontos.add(passo.nome)
        medidos.append((passo, estado))
    return medidos


def main(argv: list[str]) -> int:
    if argv[:1] == ["segredo"]:
        leitor = argparse.ArgumentParser(prog="nuvem.py segredo")
        leitor.add_argument("nome", choices=sorted(FONTES))
        leitor.add_argument("--executar", action="store_true")
        args = leitor.parse_args(argv[1:])
        return segredo(_contexto(so_projeto=True), args.nome, args.executar)
    if argv[:1] == ["prova-chat"]:
        leitor = argparse.ArgumentParser(prog="nuvem.py prova-chat")
        leitor.add_argument("mensagem", nargs="?", default="o que tenho amanhã na agenda?")
        return prova_chat(_contexto(), leitor.parse_args(argv[1:]).mensagem)
    if argv[:1] == ["deploy"]:
        leitor = argparse.ArgumentParser(prog="nuvem.py deploy")
        leitor.add_argument("--executar", action="store_true")
        return deploy(_contexto(), leitor.parse_args(argv[1:]).executar)
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--executar", choices=[p.nome for p in PASSOS])
    args = leitor.parse_args(argv)
    ctx = _contexto()
    print(f"Projeto {ctx.projeto} em {ctx.regiao} (medido agora):")
    medidos = medir(ctx)
    ctx = dataclasses.replace(ctx, prontos=frozenset(p.nome for p, e in medidos if e.pronto))
    for passo, estado in medidos:
        marca = "✅" if estado.pronto else "⬜"
        print(f"  {marca} {passo.nome:<12} {passo.descricao}: {estado.detalhe}")
        if not estado.pronto and args.executar is None:
            seta = "→" if estado.medido else "?→"
            if not estado.medido:
                print("       não medido: os comandos abaixo só valem se o recurso não existir")
            for comando in passo.comandos(ctx):
                print(f"       {seta} {_legivel(comando)}")
            if passo.irreversivel:
                print(f"       ⚠️  irreversível: {passo.irreversivel}")
    if args.executar is None:
        print("Nada foi mudado (sem --executar).")
        return 0
    (passo,) = [p for p in PASSOS if p.nome == args.executar]
    for comando in passo.comandos(ctx):
        print(f"$ {_legivel(comando)}")
        resultado = _rodar(comando)
        if resultado.returncode != 0:
            print(resultado.stderr.strip(), file=sys.stderr)
            return 1
    estado = passo.medir(ctx)
    print(f"{'✅' if estado.pronto else '⬜'} {passo.nome}: {estado.detalhe}")
    return 0 if estado.pronto else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
