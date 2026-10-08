"""O arquivo do backup (Sessão 11c, D63): o formato, só regras, sem rede nem banco.

Um JSON versionado com as coleções que a nuvem guarda e o dono quer de volta num desastre: os
lembretes (no formato fechado da migração, `reminders/transporte.py`), o registro de ações dos
últimos 30 dias (a linha inteira, `registro_interface.CAMPOS_DA_COPIA`), os gastos do teto e, desde
a versão 2 (Sessão 13, D66), os fatos da memória sem o vetor (`memoria/store.CAMPOS_DA_COPIA`) e,
desde a versão 3 (Sessão 13b, D67), as receitas (`memoria/receitas.CAMPOS_DA_COPIA`). Ele
leva as contagens e a impressão sha256 de cada lembrete: `ler` confere tudo e recusa o arquivo
inteiro se algo não bate (uma versão que não conhece, um campo a mais, uma contagem ou uma
impressão errada), sem ecoar conteúdo na mensagem.

`montar` passa o que monta por `ler` antes de devolver: um arquivo que não se lê de volta erra no
dia do backup, não no dia do desastre.

`impressao_do_conteudo` diz se o que a nuvem guarda mudou desde um backup (resposta do dono,
2026-10-07: um arquivo novo só quando algo mudou): sem o instante, o commit e as ações do próprio
backup, que senão fariam todo dia diferente do anterior.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lifeos import registro_interface
from lifeos.memoria import receitas as memoria_receitas
from lifeos.memoria import store as memoria_store
from lifeos.reminders import transporte
from lifeos.reminders.models import Reminder

# A versão 2 (Sessão 13, D66) leva a memória: os textos e as marcas, sem o vetor (que se
# reconstrói com `viking memoria --reindexar`). A versão 3 (Sessão 13b, D67) leva as receitas, todas
# (as propostas também: a TTL as apaga). Os arquivos da versão 1 e da 2 continuam se lendo.
FORMATO, VERSAO = "viking-backup", 3
VERSOES_LIDAS = (1, 2, 3)
CAMPOS_V1 = (
    "formato",
    "versao",
    "criado_em",
    "commit",
    "contagens",
    "impressoes",
    "lembretes",
    "acoes",
    "gastos",
)
CAMPOS_V2 = (*CAMPOS_V1, "memoria")
CAMPOS = (*CAMPOS_V2, "receitas")
COLECOES_V1 = ("lembretes", "acoes", "gastos")
COLECOES_V2 = (*COLECOES_V1, "memoria")
COLECOES = (*COLECOES_V2, "receitas")
# O que cada versão tem (os campos do arquivo, as coleções e as contagens).
_DA_VERSAO = {1: (CAMPOS_V1, COLECOES_V1), 2: (CAMPOS_V2, COLECOES_V2), 3: (CAMPOS, COLECOES)}
_ORIGENS_DO_FATO = memoria_store.ORIGENS
# Um pedido da restauração leva até isto de ações e meses (as ações têm a cópia para desfazer).
LOTE_DO_BACKUP = 50
CAMPOS_DO_GASTO = ("mes", "total", "dias")
# A ação que o próprio backup grava ao subir (`drive.subir`): não conta como mudança.
OPERACAO_DO_BACKUP = "backup.drive"
_MES = re.compile(r"\d{4}-\d{2}")
_DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
_TEXTOS_DA_ACAO = ("turno", "origem", "operacao", "parametros", "estado")
_OPCIONAIS_DA_ACAO = ("resultado", "erro", "desfazer")


class BackupInvalido(ValueError):
    """O arquivo não é um backup que esta versão sabe ler: nada é restaurado."""


@dataclass(frozen=True)
class Backup:
    criado_em: datetime
    commit: str
    lembretes: list[Reminder]
    acoes: list[dict[str, Any]]
    gastos: list[dict[str, Any]]
    memoria: list[dict[str, Any]] = field(default_factory=list)
    receitas: list[dict[str, Any]] = field(default_factory=list)

    def contagens(self) -> dict[str, int]:
        return {
            "lembretes": len(self.lembretes),
            "acoes": len(self.acoes),
            "gastos": len(self.gastos),
            "memoria": len(self.memoria),
            "receitas": len(self.receitas),
        }


def _instante(valor: Any, onde: str, *, obrigatorio: bool) -> str | None:
    """O texto de um instante, conferido: UTC com microssegundos, como `texto_do_instante` grava."""
    if valor is None and not obrigatorio:
        return None
    try:
        momento = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        momento = None
    if momento is None or momento.tzinfo is None:
        raise BackupInvalido(f"{onde}: tem de ser um instante ISO 8601 com fuso")
    if registro_interface.texto_do_instante(momento) != valor:
        raise BackupInvalido(f"{onde}: o instante não está em UTC com microssegundos")
    return valor


def _numero(valor: Any, onde: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or not math.isfinite(valor):
        raise BackupInvalido(f"{onde}: tem de ser um número")
    if valor < 0:
        raise BackupInvalido(f"{onde}: não pode ser negativo")
    return float(valor)


def acao_conferida(copia: Any, onde: str = "ação") -> dict[str, Any]:
    """Uma ação no formato da cópia, conferida campo a campo."""
    if not isinstance(copia, dict) or set(copia) != set(registro_interface.CAMPOS_DA_COPIA):
        raise BackupInvalido(
            f"{onde}: tem de ter exatamente os campos {list(registro_interface.CAMPOS_DA_COPIA)}"
        )
    identificador = copia["id"]
    if isinstance(identificador, bool) or not isinstance(identificador, int) or identificador <= 0:
        raise BackupInvalido(f"{onde}: o id tem de ser um inteiro positivo")
    for campo in _TEXTOS_DA_ACAO:
        if not isinstance(copia[campo], str):
            raise BackupInvalido(f"{onde}: {campo} tem de ser texto")
    for campo in _OPCIONAIS_DA_ACAO:
        if copia[campo] is not None and not isinstance(copia[campo], str):
            raise BackupInvalido(f"{onde}: {campo} tem de ser texto ou nulo")
    try:
        parametros = json.loads(copia["parametros"])
    except ValueError:
        parametros = None
    if not isinstance(parametros, dict):
        raise BackupInvalido(f"{onde}: parametros tem de ser um objeto JSON")
    for campo in registro_interface.INSTANTES_DA_COPIA:
        _instante(copia[campo], f"{onde}: {campo}", obrigatorio=campo == "criada_em")
    return dict(copia)


def gasto_conferido(copia: Any, onde: str = "gasto") -> dict[str, Any]:
    """Um mês do teto: `{"mes": "AAAA-MM", "total": n, "dias": {"AAAA-MM-DD": n}}`."""
    if not isinstance(copia, dict) or set(copia) != set(CAMPOS_DO_GASTO):
        raise BackupInvalido(f"{onde}: tem de ter exatamente os campos {list(CAMPOS_DO_GASTO)}")
    mes = copia["mes"]
    if not isinstance(mes, str) or not _MES.fullmatch(mes):
        raise BackupInvalido(f"{onde}: o mês tem de ser AAAA-MM")
    if not isinstance(copia["dias"], dict):
        raise BackupInvalido(f"{onde}: dias tem de ser um objeto")
    dias = {}
    for dia, valor in copia["dias"].items():
        if not isinstance(dia, str) or not _DIA.fullmatch(dia) or not dia.startswith(f"{mes}-"):
            raise BackupInvalido(f"{onde}: um dia fora do mês ou fora do formato AAAA-MM-DD")
        dias[dia] = _numero(valor, f"{onde}: o gasto de um dia")
    return {"mes": mes, "total": _numero(copia["total"], f"{onde}: o total"), "dias": dias}


def fato_conferido(copia: Any, onde: str = "fato") -> dict[str, Any]:
    """Um fato da memória no formato da cópia (`memoria.store.copia`), conferido campo a campo.
    O filtro do que pode virar fato não roda aqui (uma regra nova não pode fazer o backup do dia
    falhar): roda ao restaurar, no `store.importar`."""
    if not isinstance(copia, dict) or set(copia) != set(memoria_store.CAMPOS_DA_COPIA):
        raise BackupInvalido(
            f"{onde}: tem de ter exatamente os campos {list(memoria_store.CAMPOS_DA_COPIA)}"
        )
    if not memoria_store.id_valido(copia["id"]):
        raise BackupInvalido(f"{onde}: o id tem de ser um UUID")
    if not isinstance(copia["texto"], str) or not copia["texto"].strip():
        raise BackupInvalido(f"{onde}: o texto tem de ser um texto não vazio")
    if copia["origem"] not in _ORIGENS_DO_FATO:
        raise BackupInvalido(f"{onde}: origem desconhecida")
    for campo in ("sessao", "turno"):
        if not isinstance(copia[campo], str):
            raise BackupInvalido(f"{onde}: {campo} tem de ser texto")
    if not isinstance(copia["ativo"], bool):
        raise BackupInvalido(f"{onde}: ativo tem de ser verdadeiro ou falso")
    substituido_por = copia["substituido_por"]
    if substituido_por is not None and not memoria_store.id_valido(substituido_por):
        raise BackupInvalido(f"{onde}: substituido_por tem de ser um UUID ou nulo")
    for campo in ("criado_em", "invalida_em", "esquecido_em", "apagar_em"):
        _instante(copia[campo], f"{onde}: {campo}", obrigatorio=campo == "criado_em")
    return dict(copia)


def receita_conferida(copia: Any, onde: str = "receita") -> dict[str, Any]:
    """Uma receita no formato da cópia (`memoria.receitas.copia`), conferida campo a campo. O filtro
    das receitas roda ao restaurar (`receitas.importar`), como o dos fatos."""
    if not isinstance(copia, dict) or set(copia) != set(memoria_receitas.CAMPOS_DA_COPIA):
        raise BackupInvalido(
            f"{onde}: tem de ter exatamente os campos {list(memoria_receitas.CAMPOS_DA_COPIA)}"
        )
    if not memoria_receitas.id_valido(copia["id"]):
        raise BackupInvalido(f"{onde}: o id tem de ser um UUID")
    if not isinstance(copia["nome"], str) or not copia["nome"].strip():
        raise BackupInvalido(f"{onde}: o nome tem de ser um texto não vazio")
    passos = copia["passos"]
    if not isinstance(passos, list) or not passos or not all(isinstance(p, str) for p in passos):
        raise BackupInvalido(f"{onde}: passos tem de ser uma lista de textos")
    if copia["estado"] not in memoria_receitas.ESTADOS:
        raise BackupInvalido(f"{onde}: estado desconhecido")
    if copia["origem"] not in memoria_receitas.ORIGENS:
        raise BackupInvalido(f"{onde}: origem desconhecida")
    for campo in ("sessao", "turno"):
        if not isinstance(copia[campo], str):
            raise BackupInvalido(f"{onde}: {campo} tem de ser texto")
    if not isinstance(copia["ativo"], bool):
        raise BackupInvalido(f"{onde}: ativo tem de ser verdadeiro ou falso")
    substituido_por = copia["substituido_por"]
    if substituido_por is not None and not memoria_receitas.id_valido(substituido_por):
        raise BackupInvalido(f"{onde}: substituido_por tem de ser um UUID ou nulo")
    for campo in ("criado_em", "guardada_em", "invalida_em", "esquecido_em", "apagar_em"):
        _instante(copia[campo], f"{onde}: {campo}", obrigatorio=campo == "criado_em")
    return {**copia, "passos": list(passos)}


def _sem_repetir(ids: list[Any], colecao: str) -> None:
    if len(set(ids)) != len(ids):
        raise BackupInvalido(f"{colecao}: um id aparece duas vezes")


def ler(dados: Any) -> Backup:
    """O backup conferido inteiro, ou `BackupInvalido` (sem ecoar conteúdo)."""
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
        raise BackupInvalido("não é um arquivo de backup do Viking")
    versao = dados.get("versao")
    if isinstance(versao, bool) or versao not in VERSOES_LIDAS:
        raise BackupInvalido(f"versão do backup desconhecida (esta lê {list(VERSOES_LIDAS)})")
    campos, colecoes = _DA_VERSAO[versao]
    if set(dados) != set(campos):
        raise BackupInvalido(f"o backup tem de ter exatamente os campos {list(campos)}")
    criado_em = _instante(dados["criado_em"], "criado_em", obrigatorio=True)
    assert criado_em is not None
    if not isinstance(dados["commit"], str):
        raise BackupInvalido("commit tem de ser texto")
    for colecao in colecoes:
        if not isinstance(dados[colecao], list):
            raise BackupInvalido(f"{colecao} tem de ser uma lista")

    lembretes = []
    for n, item in enumerate(dados["lembretes"], 1):
        try:
            lembretes.append(transporte.de_dict(item))
        except transporte.LembreteInvalido as exc:
            raise BackupInvalido(f"lembrete {n}: {exc}") from None
    acoes = [acao_conferida(a, f"ação {n}") for n, a in enumerate(dados["acoes"], 1)]
    gastos = [gasto_conferido(g, f"gasto {n}") for n, g in enumerate(dados["gastos"], 1)]
    memoria = [fato_conferido(f, f"fato {n}") for n, f in enumerate(dados.get("memoria", []), 1)]
    receitas = [
        receita_conferida(r, f"receita {n}") for n, r in enumerate(dados.get("receitas", []), 1)
    ]
    _sem_repetir([r.id for r in lembretes], "lembretes")
    _sem_repetir([a["id"] for a in acoes], "ações")
    _sem_repetir([g["mes"] for g in gastos], "gastos")
    _sem_repetir([f["id"] for f in memoria], "memória")
    _sem_repetir([r["id"] for r in receitas], "receitas")

    backup = Backup(
        criado_em=datetime.fromisoformat(criado_em).astimezone(UTC),
        commit=dados["commit"],
        lembretes=lembretes,
        acoes=acoes,
        gastos=gastos,
        memoria=memoria,
        receitas=receitas,
    )
    contagens = {c: n for c, n in backup.contagens().items() if c in colecoes}
    if dados["contagens"] != contagens:
        raise BackupInvalido("as contagens do backup não batem com o conteúdo")
    impressoes = {str(r.id): transporte.impressao(r) for r in lembretes}
    if dados["impressoes"] != impressoes:
        raise BackupInvalido("a impressão de algum lembrete não bate: o arquivo foi alterado")
    return backup


def montar(
    lembretes: list[Reminder],
    acoes: list[dict[str, Any]],
    gastos: list[dict[str, Any]],
    *,
    agora: datetime,
    commit: str,
    memoria: list[dict[str, Any]] | None = None,
    receitas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """O conteúdo do arquivo, já lido de volta (`ler`) antes de sair daqui."""
    memoria, receitas = list(memoria or []), list(receitas or [])
    dados = {
        "formato": FORMATO,
        "versao": VERSAO,
        "criado_em": registro_interface.texto_do_instante(agora),
        "commit": commit,
        "contagens": {
            "lembretes": len(lembretes),
            "acoes": len(acoes),
            "gastos": len(gastos),
            "memoria": len(memoria),
            "receitas": len(receitas),
        },
        "impressoes": {str(r.id): transporte.impressao(r) for r in lembretes},
        "lembretes": [transporte.para_dict(r) for r in lembretes],
        "acoes": [dict(a) for a in acoes],
        "gastos": [dict(g) for g in gastos],
        "memoria": [dict(f) for f in memoria],
        "receitas": [dict(r) for r in receitas],
    }
    ler(dados)
    return dados


def impressao_do_conteudo(backup: Backup) -> str:
    """O sha256 do que o backup guarda, na ordem dos ids: sem o instante, o commit e as ações do
    próprio backup (`OPERACAO_DO_BACKUP`). Igual = nada mudou desde aquele arquivo."""
    conteudo = {
        "lembretes": sorted(
            (transporte.para_dict(r) for r in backup.lembretes), key=lambda d: d["id"]
        ),
        "acoes": sorted(
            (a for a in backup.acoes if a["operacao"] != OPERACAO_DO_BACKUP), key=lambda a: a["id"]
        ),
        "gastos": sorted(backup.gastos, key=lambda g: g["mes"]),
        "memoria": sorted(backup.memoria, key=lambda f: f["id"]),
        "receitas": sorted(backup.receitas, key=lambda r: r["id"]),
    }
    texto = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def para_bytes(dados: dict[str, Any]) -> bytes:
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")


def de_bytes(conteudo: bytes) -> Backup:
    try:
        dados = json.loads(conteudo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BackupInvalido("o arquivo não é JSON") from None
    return ler(dados)


def nome_do_arquivo(agora: datetime) -> str:
    """`viking-backup-AAAA-MM-DDTHHMMZ.json`, em UTC: dois no mesmo dia não colidem."""
    return f"viking-backup-{agora.astimezone(UTC):%Y-%m-%dT%H%MZ}.json"
