"""A infraestrutura do Viking no GCP, como script (Sessão 10, D58; skill `nuvem-e-deploy` §6).

**Sem flag, só lê:** mede cada passo no projeto de verdade e imprime o que existe, o que falta e o
comando que criaria. **Com `--executar PASSO`**, roda os comandos daquele passo e mede de novo.
O ok do dono vem antes, na conversa, passo a passo: criar recurso ou gastar é decisão dele.

    python scripts/nuvem.py                       (só lê)
    python scripts/nuvem.py --executar projeto    (um passo)

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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lifeos import config
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
MOTOR, CLI = "motor", "cli"  # contas de serviço


class ErroDoGcloud(RuntimeError):
    pass


@dataclass(frozen=True)
class Contexto:
    projeto: str
    regiao: str
    faturamento: str
    orcamento: str
    dono: str  # a conta do gcloud (e-mail): só em memória, para o papel no `cli@`
    projeto_existe: bool = True  # sem projeto, os passos compostos não leem nada para listar

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


_NAO_EXISTE = ("NOT_FOUND", "not found", "does not exist", "may not exist", "was not found")


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
    existe = ctx.projeto_existe and _ler(
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
        if not ctx.projeto_existe
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
    faltam = [
        f"{c}: {campos}" for c, campos in store_firestore.INDICES if (c, campos) not in existentes
    ]
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
            *(
                f"--field-config=field-path={campo},order={ordem.lower()}"
                for campo, ordem in campos
            ),
        )
        for colecao, campos in store_firestore.INDICES
    ]


PASSOS = (
    Passo("projeto", "o projeto só do Viking", _m_projeto, _c_projeto),
    Passo("faturamento", "o faturamento do dono ligado", _m_faturamento, _c_faturamento),
    Passo("apis", "as APIs que o Viking usa", _m_apis, _c_apis),
    Passo("orcamento", "orçamento com alertas (só avisa)", _m_orcamento, _c_orcamento),
    Passo(
        "firestore",
        "o banco (default), nativo",
        _m_firestore,
        _c_firestore,
        irreversivel="o local do Firestore não muda depois de criado",
    ),
    Passo("registro", "Artifact Registry das imagens", _m_registro, _c_registro),
    Passo("contas", "contas de serviço e papéis", _m_contas, _c_contas),
    Passo("indices", "índices compostos do Firestore", _m_indices, _c_indices),
)


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
    medidos: list[tuple[Passo, Estado]] = []
    for passo in PASSOS:
        if medidos and not medidos[0][1].pronto:  # sem o projeto, nada mais existe
            medidos.append((passo, Estado(False, "depende do projeto")))
            continue
        medidos.append((passo, passo.medir(ctx)))
    return medidos


def main(argv: list[str]) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--executar", choices=[p.nome for p in PASSOS])
    args = leitor.parse_args(argv)
    ctx = _contexto()
    print(f"Projeto {ctx.projeto} em {ctx.regiao} (medido agora):")
    medidos = medir(ctx)
    ctx = dataclasses.replace(ctx, projeto_existe=medidos[0][1].pronto)
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
