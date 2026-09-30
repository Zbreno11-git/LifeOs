"""A infraestrutura do Viking no GCP, como script (Sessão 10, D58; skill `nuvem-e-deploy` §6).

**Sem flag, só lê:** mede cada passo no projeto de verdade e imprime o que existe, o que falta e o
comando que criaria. **Com `--executar PASSO`**, roda os comandos daquele passo e mede de novo.
O ok do dono vem antes, na conversa, passo a passo: criar recurso ou gastar é decisão dele.

    python scripts/nuvem.py                       (só lê)
    python scripts/nuvem.py --executar projeto    (um passo)
    python scripts/nuvem.py deploy                (o que está no ar, o que mudou, e as provas)
    python scripts/nuvem.py deploy --executar     (constrói, envia, publica e prova)

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
)
REPOSITORIO = "viking"  # Artifact Registry
GUARDAR_IMAGENS = 5
ORCAMENTO_NOME = "viking"
ALERTAS = (0.5, 0.9, 1.0)
MOTOR, CLI = "viking-motor", "viking-cli"  # contas de serviço (o ID pede de 6 a 30 letras)
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


def _rodar(comando: list[str]) -> subprocess.CompletedProcess:
    if comando[0] != "gcloud" or not any(a.startswith("--project=") for a in comando):
        raise ErroDoGcloud(f"comando fora de _gcloud: {comando[:3]}")
    return subprocess.run(comando, capture_output=True, text=True, check=False, timeout=300)


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
    for nome in (MOTOR, CLI):
        if _ler(_gcloud(ctx, "iam", "service-accounts", "describe", ctx.conta(nome))) is None:
            faltam.append(f"{nome}@")
    if faltam:
        return Estado(False, "faltam: " + ", ".join(faltam))
    projeto = _ler(_gcloud(ctx, "projects", "get-iam-policy", ctx.projeto))
    if f"serviceAccount:{ctx.conta(MOTOR)}" not in _membros(projeto, "roles/datastore.user"):
        return Estado(False, "motor@ sem roles/datastore.user")
    cli = _ler(_gcloud(ctx, "iam", "service-accounts", "get-iam-policy", ctx.conta(CLI)))
    if f"user:{ctx.dono}" not in _membros(cli, "roles/iam.serviceAccountTokenCreator"):
        return Estado(False, "o dono ainda não pode pedir token do cli@")
    return Estado(True, "motor@ (Firestore), cli@ (o dono pede o token)")


def _c_contas(ctx: Contexto) -> list[list[str]]:
    """Só cria a conta que falta (repetir o passo não esbarra no "já existe"); os papéis são
    idempotentes no próprio IAM."""
    nomes = {MOTOR: "Viking: identidade do motor", CLI: "Viking: o terminal do dono"}
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
        _gcloud(
            ctx,
            "iam",
            "service-accounts",
            "add-iam-policy-binding",
            ctx.conta(CLI),
            f"--member=user:{ctx.dono}",
            "--role=roles/iam.serviceAccountTokenCreator",
        ),
    ]


def _campos_do_indice(indice: dict) -> tuple[tuple[str, str], ...]:
    return tuple(
        (c["fieldPath"], c.get("order", ""))
        for c in indice.get("fields", [])
        if c["fieldPath"] != "__name__"
    )


def _m_indices(ctx: Contexto) -> Estado:
    dados = _ler(_gcloud(ctx, "firestore", "indexes", "composite", "list", "--database=(default)"))
    existentes = {
        (i.get("name", "").split("/collectionGroups/")[-1].split("/")[0], _campos_do_indice(i))
        for i in dados or []
        if i.get("state") == "READY"
    }
    faltam = [f"{c}: {campos}" for c, campos in INDICES if (c, campos) not in existentes]
    return Estado(
        not faltam, "prontos" if not faltam else "faltam (ou construindo): " + "; ".join(faltam)
    )


def _c_indices(ctx: Contexto) -> list[list[str]]:
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
    ]


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
    if isinstance(servico, dict):
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


def comandos_do_deploy(ctx: Contexto, sha: str) -> list[list[str]]:
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
            "--timeout=60",
            "--labels=app=viking",
            "--set-env-vars="
            + ",".join(
                [
                    f"VIKING_NUVEM_PROJETO={ctx.projeto}",
                    f"VIKING_NUVEM_URL={_url(ctx)}",
                    f"VIKING_TIMEZONE={_fuso()}",
                ]
            ),
        ),
        _gcloud(
            ctx,
            "run",
            "services",
            "add-iam-policy-binding",
            SERVICO,
            f"--region={ctx.regiao}",
            f"--member=serviceAccount:{ctx.conta(CLI)}",
            "--role=roles/run.invoker",
        ),
    ]


def _token(ctx: Contexto, *args: str) -> str:
    """Um token do gcloud, que nunca é impresso nem gravado: vai para o `docker login` pela entrada
    padrão ou para o cabeçalho de um pedido."""
    resultado = _rodar(_gcloud(ctx, "auth", *args))
    if resultado.returncode != 0 or not resultado.stdout.strip():
        raise ErroDoGcloud(f"auth {args[0]}: {resultado.stderr.strip()[-200:]}")
    return resultado.stdout.strip()


def publicar(ctx: Contexto, sha: str) -> None:
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
    for comando in comandos_do_deploy(ctx, sha):
        print(f"$ {_legivel(comando)}")
        resultado = _rodar(comando)
        if resultado.returncode != 0:
            raise ErroDoGcloud(resultado.stderr.strip()[-400:])


@dataclass(frozen=True)
class Prova:
    nome: str
    passou: bool
    detalhe: str


def provas(ctx: Contexto, sha: str) -> list[Prova]:
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
    certo = quem == {f"serviceAccount:{ctx.conta(CLI)}"}
    resultado.append(Prova("só o viking-cli@ invoca", certo, ", ".join(sorted(quem)) or "ninguém"))

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
    for rota in ("/lembretes", "/fumaca/vencidos"):
        resposta = requests.get(f"{url}{rota}", headers=cabecalho, timeout=60)
        resultado.append(
            Prova(
                f"viking-cli@: {rota}", resposta.status_code == 200, f"HTTP {resposta.status_code}"
            )
        )

    filtro = (
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICO}" '
        "AND severity>=ERROR"
    )
    erros = _ler(_gcloud(ctx, "logging", "read", filtro, "--freshness=30m", "--limit=20"))
    resultado.append(Prova("log sem erro (30 min)", not erros, f"{len(erros or [])} erro(s)"))
    return resultado


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
    # Nada nos caminhos da imagem desde a que está no ar: ela já é o código de agora, e publicar
    # de novo só trocaria a etiqueta (skill `nuvem-e-deploy` §4, a segunda pergunta).
    em_dia = agora.no_ar is not None and agora.mudou_desde == 0
    esperado = agora.no_ar if em_dia and agora.no_ar else agora.head
    if executar:
        if not pode:
            print("Não publico: a imagem tem de ser um commit limpo, no GitHub e com CI verde.")
            return 1
        if em_dia:
            print("Nada mudou na imagem desde a que está no ar; só as provas.")
        else:
            publicar(ctx, agora.head)
    elif not em_dia:
        for comando in comandos_do_deploy(ctx, agora.head):
            print(f"  → {_legivel(comando)}")
        print("Nada foi publicado (sem --executar).")
    print("Provas (rodam sempre):")
    feitas = provas(ctx, esperado)
    for prova in feitas:
        print(f"  {'✅' if prova.passou else '❌'} {prova.nome}: {prova.detalhe}")
    return 0 if all(p.passou for p in feitas) else 2


# --- a linha de comando ------------------------------------------------------------------------


def _contexto() -> Contexto:
    faltam = [
        nome
        for nome in ("VIKING_NUVEM_PROJETO", "VIKING_NUVEM_FATURAMENTO", "VIKING_NUVEM_ORCAMENTO")
        if not os.getenv(nome)
    ]
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
        faturamento=os.environ["VIKING_NUVEM_FATURAMENTO"],
        orcamento=os.environ["VIKING_NUVEM_ORCAMENTO"],
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
        estado = Estado(False, f"depende de {', '.join(faltam)}") if faltam else passo.medir(ctx)
        if estado.pronto:
            prontos.add(passo.nome)
        medidos.append((passo, estado))
    return medidos


def main(argv: list[str]) -> int:
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
            for comando in passo.comandos(ctx):
                print(f"       → {_legivel(comando)}")
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
