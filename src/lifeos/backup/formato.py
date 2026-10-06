"""O arquivo do backup (Sessão 11c, D63): o formato, só regras, sem rede nem banco.

Um JSON versionado com as três coleções que a nuvem guarda e o dono quer de volta num desastre:
os lembretes (no formato fechado da migração, `reminders/transporte.py`), o registro de ações dos
últimos 30 dias (a linha inteira, `registro_interface.CAMPOS_DA_COPIA`) e os gastos do teto. Ele
leva as contagens e a impressão sha256 de cada lembrete: `ler` confere tudo e recusa o arquivo
inteiro se algo não bate (uma versão que não conhece, um campo a mais, uma contagem ou uma
impressão errada), sem ecoar conteúdo na mensagem.

`montar` passa o que monta por `ler` antes de devolver: um arquivo que não se lê de volta erra no
dia do backup, não no dia do desastre.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lifeos import registro_interface
from lifeos.reminders import transporte
from lifeos.reminders.models import Reminder

FORMATO, VERSAO = "viking-backup", 1
CAMPOS = (
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
COLECOES = ("lembretes", "acoes", "gastos")
CAMPOS_DO_GASTO = ("mes", "total", "dias")
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

    def contagens(self) -> dict[str, int]:
        return {
            "lembretes": len(self.lembretes),
            "acoes": len(self.acoes),
            "gastos": len(self.gastos),
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


def _sem_repetir(ids: list[Any], colecao: str) -> None:
    if len(set(ids)) != len(ids):
        raise BackupInvalido(f"{colecao}: um id aparece duas vezes")


def ler(dados: Any) -> Backup:
    """O backup conferido inteiro, ou `BackupInvalido` (sem ecoar conteúdo)."""
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
        raise BackupInvalido("não é um arquivo de backup do Viking")
    if dados.get("versao") != VERSAO:
        raise BackupInvalido(f"versão do backup desconhecida (esta lê a {VERSAO})")
    if set(dados) != set(CAMPOS):
        raise BackupInvalido(f"o backup tem de ter exatamente os campos {list(CAMPOS)}")
    criado_em = _instante(dados["criado_em"], "criado_em", obrigatorio=True)
    assert criado_em is not None
    if not isinstance(dados["commit"], str):
        raise BackupInvalido("commit tem de ser texto")
    for colecao in COLECOES:
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
    _sem_repetir([r.id for r in lembretes], "lembretes")
    _sem_repetir([a["id"] for a in acoes], "ações")
    _sem_repetir([g["mes"] for g in gastos], "gastos")

    backup = Backup(
        criado_em=datetime.fromisoformat(criado_em).astimezone(UTC),
        commit=dados["commit"],
        lembretes=lembretes,
        acoes=acoes,
        gastos=gastos,
    )
    if dados["contagens"] != backup.contagens():
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
) -> dict[str, Any]:
    """O conteúdo do arquivo, já lido de volta (`ler`) antes de sair daqui."""
    dados = {
        "formato": FORMATO,
        "versao": VERSAO,
        "criado_em": registro_interface.texto_do_instante(agora),
        "commit": commit,
        "contagens": {"lembretes": len(lembretes), "acoes": len(acoes), "gastos": len(gastos)},
        "impressoes": {str(r.id): transporte.impressao(r) for r in lembretes},
        "lembretes": [transporte.para_dict(r) for r in lembretes],
        "acoes": [dict(a) for a in acoes],
        "gastos": [dict(g) for g in gastos],
    }
    ler(dados)
    return dados


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
