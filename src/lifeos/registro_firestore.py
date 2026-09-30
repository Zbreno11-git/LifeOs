"""O registro de ações no Firestore (Sessão 10b, D57/D59): a implementação da nuvem de
`registro_interface.Registro`, que passa o mesmo contrato do SQLite (`tests/test_registro.py`, no
emulador). A regra mora em `registro.py`; aqui só se guarda e se busca.

Onde o Firestore difere do SQLite, e o que fazemos:
- **não há contador:** o id é o relógio em nanossegundos na hora de nascer, gravado com `create()`
  (um id que já existe tenta o seguinte, nunca sobrescreve). Cresce na ordem em que as ações
  nascem, que é o que o `desfaz` e o aviso depois de um erro leem;
- **a retenção é a TTL nativa** no campo `expira_em` (`scripts/nuvem.py`, passo `ttl`). Ela apaga
  com atraso, então toda leitura também corta pelo `desde` que `registro.py` passa;
- **consulta com um campo só**, e o resto filtrado aqui: o único índice composto é o de
  `contaveis` (`INDICES`); o emulador não exige índice e a produção exige, então a rota de fumaça
  do motor exerce cada consulta no ar;
- **desfazer uma vez só** por comparar e trocar (`firestore_comum.trocar`);
- **todo documento inteiro**, e um documento parcial erra alto na leitura.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum
from lifeos.registro_interface import FALHOU, FEITA, Acao

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "acoes"
# Quanto depois de nascer a TTL pode apagar: igual à retenção de `registro.py` (um teste amarra).
VIDA = timedelta(days=30)
# (coleção, ((campo, ordem), …)): o que `contaveis` pede (igualdade na operação e intervalo no
# instante). `scripts/nuvem.py` cria e confere; mude os dois juntos com a consulta.
INDICES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (COLECAO, (("operacao", "ASCENDING"), ("criada_em", "ASCENDING"))),
)
_CAMPOS = (
    "id",
    "turno",
    "origem",
    "operacao",
    "parametros",
    "estado",
    "resultado",
    "erro",
    "desfazer",
    "desfeita_em",
    "criada_em",
    "terminada_em",
    "expira_em",
)


def _colecao() -> Any:
    return firestore_comum.cliente().collection(COLECAO)


def _ref(acao_id: int) -> DocumentReference:
    return _colecao().document(str(int(acao_id)))


def _acao(snap: DocumentSnapshot) -> Acao:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, não lê pela metade
        raise ValueError(f"ação {snap.id} sem os campos {faltam}")
    criada_em = firestore_comum.lido(dados["criada_em"])
    assert criada_em is not None
    return Acao(
        id=int(dados["id"]),
        turno=dados["turno"],
        origem=dados["origem"],
        operacao=dados["operacao"],
        parametros=json.loads(dados["parametros"]),
        estado=dados["estado"],
        resultado=json.loads(dados["resultado"]) if dados["resultado"] else {},
        erro=dados["erro"] or "",
        desfazivel=bool(dados["desfazer"]) and dados["desfeita_em"] is None,
        desfeita_em=firestore_comum.lido(dados["desfeita_em"]),
        criada_em=criada_em,
    )


def _vivas(snaps: Any, desde: datetime) -> list[Acao]:
    """As que nasceram desde `desde` (a TTL apaga com atraso), na ordem em que nasceram."""
    corte = firestore_comum.instante(desde)
    return sorted((a for a in map(_acao, snaps) if a.criada_em >= corte), key=lambda a: a.id)


def purgar(antes_de: datetime) -> None:
    """Nada: quem apaga é a TTL em `expira_em`, e a leitura corta pelo `desde`."""
    firestore_comum.instante(antes_de)


def iniciar(*, turno: str, origem: str, operacao: str, parametros: str, criada_em: datetime) -> int:
    from google.api_core.exceptions import AlreadyExists

    criada_em = firestore_comum.instante(criada_em)
    acao_id = time.time_ns()
    for _ in range(100):
        documento = dict.fromkeys(_CAMPOS)
        documento.update(
            id=acao_id,
            turno=turno,
            origem=origem,
            operacao=operacao,
            parametros=parametros,
            estado="iniciada",
            erro="",
            criada_em=criada_em,
            expira_em=criada_em + VIDA,
        )
        try:
            _ref(acao_id).create(documento)
        except AlreadyExists:
            acao_id = max(acao_id + 1, time.time_ns())  # outra ação nasceu no mesmo instante
            continue
        return acao_id
    raise RuntimeError("não achei um id livre para a ação em 100 tentativas")


def terminar(
    acao_id: int,
    *,
    estado: str,
    resultado: str,
    erro: str,
    desfazer: str | None,
    terminada_em: datetime,
) -> None:
    _ref(acao_id).update(
        {
            "estado": estado,
            "resultado": resultado,
            "erro": erro,
            "desfazer": desfazer,
            "terminada_em": firestore_comum.instante(terminada_em),
        }
    )


def do_turno(turno: str, *, desde: datetime) -> list[Acao]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("turno", "==", turno))
    return _vivas(consulta.stream(), desde)


def recentes(*, desde: datetime, limite: int) -> list[Acao]:
    from google.cloud.firestore import FieldFilter

    corte = firestore_comum.instante(desde)
    consulta = _colecao().where(filter=FieldFilter("criada_em", ">=", corte))
    return list(reversed(_vivas(consulta.stream(), desde)))[:limite]


def contaveis(operacao: str, *, desde: datetime) -> list[Acao]:
    from google.cloud.firestore import FieldFilter

    corte = firestore_comum.instante(desde)
    consulta = (
        _colecao()
        .where(filter=FieldFilter("operacao", "==", operacao))
        .where(filter=FieldFilter("criada_em", ">=", corte))
    )
    return [a for a in _vivas(consulta.stream(), desde) if a.estado != FALHOU]


def obter(acao_id: int, *, desde: datetime) -> Acao | None:
    snap = _ref(acao_id).get()
    if not snap.exists:
        return None
    vivas = _vivas([snap], desde)
    return vivas[0] if vivas else None


def _depois_do_prefixo(prefixo: str) -> str:
    """O menor texto maior que todo texto que começa com `prefixo`: o fim do intervalo."""
    return prefixo[:-1] + chr(ord(prefixo[-1]) + 1)


def ultima_desfazivel(
    operacoes: tuple[str, ...], *, prefixo_turno: str, desde: datetime
) -> Acao | None:
    from google.cloud.firestore import FieldFilter

    if not prefixo_turno or not operacoes:
        return None
    consulta = (
        _colecao()
        .where(filter=FieldFilter("turno", ">=", prefixo_turno))
        .where(filter=FieldFilter("turno", "<", _depois_do_prefixo(prefixo_turno)))
    )
    candidatas = [
        a
        for a in _vivas(consulta.stream(), desde)
        if a.operacao in operacoes
        and a.estado == FEITA
        and a.desfazivel
        and a.turno.startswith(prefixo_turno)
    ]
    return candidatas[-1] if candidatas else None


def reivindicar_desfazer(acao_id: int, *, agora: datetime) -> str | None:
    agora = firestore_comum.instante(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, str | None]:
        if not snap.exists:
            return None, None
        if snap.get("estado") != FEITA or snap.get("desfazer") is None:
            return None, None
        if snap.get("desfeita_em") is not None:
            return None, None
        return {"desfeita_em": agora}, snap.get("desfazer")

    return firestore_comum.trocar(_ref(acao_id), decidir)


def devolver_desfazer(acao_id: int) -> None:
    ref = _ref(acao_id)
    if ref.get().exists:
        ref.update({"desfeita_em": None})
