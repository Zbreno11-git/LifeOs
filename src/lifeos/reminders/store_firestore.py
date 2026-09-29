"""Os lembretes no Firestore (Sessão 10, D58): a implementação da nuvem de `reminders/interface.py`,
que passa o mesmo contrato do SQLite (`tests/test_reminders_contrato.py`, no emulador).

Onde o Firestore difere do SQLite, e o que fazemos:
- **não há `UPDATE … WHERE`**: concluir e a reserva de envio leem, decidem e gravam só se o
  documento não mudou desde a leitura (`_trocar`, comparar e trocar); quem perde relê o estado já
  decidido. Transação foi medida e recusada (lock timeout com execuções juntas);
- **`== None` não casa campo ausente**: todo documento nasce com todos os campos, `None`
  explícito (`_documento`), e nada grava um documento parcial;
- **o id vira caminho**: `document("a/b")` seria outro documento. Só se aceita um UUID
  (`_ref`), aqui e no `get`/`complete` que vêm do chat e do MCP;
- **instantes** são `Timestamp` nativos (UTC, microssegundos): nada de texto de largura fixa;
- **consulta com igualdade + intervalo pede índice composto** na produção (o emulador não pede):
  `INDICES` é a fonte que `scripts/nuvem.py` cria e confere.

Só roda onde o extra `nuvem` está instalado (Linux: o motor, o VPS, o CI); o import do SDK é
preguiçoso. Sob pytest, nenhum cliente nasce sem `FIRESTORE_EMULATOR_HOST`: o VPS tem o login do
dono vivo, e um cliente sem emulador gravaria no Firestore de verdade.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lifeos import config
from lifeos.reminders import interface
from lifeos.reminders.models import Reminder

if TYPE_CHECKING:
    from google.cloud.firestore import Client, DocumentReference, DocumentSnapshot

COLECAO = "lembretes"
# (coleção, ((campo, ordem), …)): o que `vencidos`/`atrasados` pedem (igualdade em dois campos e
# intervalo no prazo). `scripts/nuvem.py` cria e confere; mude os dois juntos com a consulta.
INDICES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        COLECAO,
        (("completed_at", "ASCENDING"), ("enviado_em", "ASCENDING"), ("due_at", "ASCENDING")),
    ),
)
_CAMPOS = (
    "type",
    "title",
    "body",
    "tags",
    "due_at",
    "completed_at",
    "source",
    "external_id",
    "metadata",
    "created_at",
    "updated_at",
    "enviado_em",
    "envio_estado",
    "envio_reservado_por",
    "envio_reservado_ate",
)

_CLIENTE: Client | None = None


def _cliente() -> Client:
    global _CLIENTE
    if _CLIENTE is None:
        emulador = os.getenv("FIRESTORE_EMULATOR_HOST")
        if "pytest" in sys.modules and not emulador:
            raise RuntimeError(
                "sob pytest o Firestore só abre no emulador (FIRESTORE_EMULATOR_HOST)"
            )
        projeto = config.NUVEM_PROJETO or ("viking-emulador" if emulador else "")
        if not projeto:
            raise RuntimeError(
                "VIKING_NUVEM_PROJETO vazio: o Firestore não sabe em que projeto abrir"
            )
        from google.cloud import firestore

        _CLIENTE = firestore.Client(project=projeto, database="(default)")
    return _CLIENTE


def _ref(reminder_id: str) -> DocumentReference | None:
    """O documento de um id, ou `None` se o id não é um UUID (e não pode virar outro caminho)."""
    if not interface.id_valido(reminder_id):
        return None
    return _cliente().collection(COLECAO).document(reminder_id)


def _instante(momento: datetime) -> datetime:
    """Só instantes: sem fuso é recusado (a borda converte, `service.py`)."""
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("horário sem fuso: o store só grava instantes (converta na borda)")
    return momento.astimezone(UTC)


def _lido(valor: Any) -> datetime | None:
    """O `Timestamp` do Firestore volta como uma subclasse de `datetime`: vira um `datetime` comum
    em UTC, com os microssegundos."""
    if valor is None:
        return None
    utc = valor.astimezone(UTC)
    return datetime(
        utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second, utc.microsecond, tzinfo=UTC
    )


def _agora() -> datetime:
    return datetime.now(UTC)


def _lembrete(snap: DocumentSnapshot) -> Reminder:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, não lê pela metade
        raise ValueError(f"lembrete {snap.id} sem os campos {faltam}")
    return Reminder(
        id=snap.id,
        type=dados["type"],
        title=dados["title"],
        body=dados["body"],
        tags=list(dados["tags"]),
        due_at=_lido(dados["due_at"]),
        completed_at=_lido(dados["completed_at"]),
        source=dados["source"],
        external_id=dados["external_id"],
        metadata=dict(dados["metadata"]),
        created_at=_lido(dados["created_at"]),
        updated_at=_lido(dados["updated_at"]),
        enviado_em=_lido(dados["enviado_em"]),
        envio_estado=dados["envio_estado"],
    )


def _documento(**campos: Any) -> dict[str, Any]:
    """Um documento inteiro: todo campo presente, `None` explícito no que não tem valor."""
    documento = dict.fromkeys(_CAMPOS)
    documento.update(campos)
    assert set(documento) == set(_CAMPOS), set(documento) ^ set(_CAMPOS)
    return documento


def add(
    title: str,
    body: str = "",
    type: str = "reminder",
    tags: list[str] | None = None,
    due_at: datetime | None = None,
    source: str = "manual",
    external_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    id: str | None = None,
) -> Reminder:
    from google.api_core.exceptions import AlreadyExists

    prazo = _instante(due_at) if due_at is not None else None  # recusa antes de abrir o banco
    reminder_id = str(uuid.uuid4()) if id is None else id
    ref = _ref(reminder_id)
    if ref is None:
        raise ValueError(f"id de lembrete tem de ser um UUID: {reminder_id!r}")
    agora = _agora()
    try:
        ref.create(
            _documento(
                type=type,
                title=title,
                body=body,
                tags=list(tags or []),
                due_at=prazo,
                source=source,
                external_id=external_id,
                metadata=dict(metadata or {}),
                created_at=agora,
                updated_at=agora,
            )
        )
    except AlreadyExists:
        pass  # retentativa com o mesmo id: devolve o que existe, sem mudar nada
    snap = ref.get()
    if not snap.exists:  # gravado sem erro e não volta: erra alto, nunca "criado" sem prova
        raise RuntimeError("o lembrete gravado não voltou do Firestore")
    return _lembrete(snap)


def get(reminder_id: str) -> Reminder | None:
    ref = _ref(reminder_id)
    if ref is None:
        return None
    snap = ref.get()
    return _lembrete(snap) if snap.exists else None


def _pela_ordem(lembretes: list[Reminder]) -> list[Reminder]:
    """A ordem do SQLite: pelo prazo, os sem prazo no fim, e o mais antigo primeiro no empate."""
    fim = datetime.max.replace(tzinfo=UTC)
    return sorted(lembretes, key=lambda r: (r.due_at is None, r.due_at or fim, r.created_at))


def list_open(type: str | None = None) -> list[Reminder]:
    from google.cloud.firestore import FieldFilter

    consulta = _cliente().collection(COLECAO).where(filter=FieldFilter("completed_at", "==", None))
    if type:
        consulta = consulta.where(filter=FieldFilter("type", "==", type))
    return _pela_ordem([_lembrete(s) for s in consulta.stream()])


TENTATIVAS = 20  # cada volta perdida é uma escrita de outra execução que deu certo


class PerdeuADisputa(RuntimeError):
    """O documento mudou entre a leitura e a escrita em todas as tentativas."""


def _trocar(ref: DocumentReference, decidir: Any) -> Any:
    """Comparar e trocar: lê sem travar, `decidir(snap)` devolve `(mudança ou None, resposta)`, e a
    mudança só grava se o documento não mudou desde a leitura (`last_update_time`). Se mudou, outra
    execução gravou antes: lê de novo e decide sobre o estado novo.

    Não é transação de propósito (medido no emulador em 2026-09-29): com 16 execuções juntas, a
    transação trava o documento para cada leitor, as escritas se esperam até "Transaction lock
    timeout", e em 5 de 10 rodadas quem desistia não achava vencedor nenhum. Aqui cada volta
    perdida quer dizer que outra execução gravou, então a disputa sempre termina."""
    import random
    import time

    from google.api_core.exceptions import Aborted, FailedPrecondition

    for tentativa in range(TENTATIVAS):
        snap = ref.get()
        mudanca, resposta = decidir(snap)
        if mudanca is None:
            return resposta
        opcao = _cliente().write_option(last_update_time=snap.update_time)
        try:
            ref.update(mudanca, option=opcao)
        except FailedPrecondition:
            continue  # outra execução gravou depois da leitura: o estado novo decide
        except Aborted:
            # A escrita não foi aplicada (escritas juntas no mesmo documento; o emulador responde
            # "Transaction lock timeout"), mas isso não prova que outra venceu: espera um pouco,
            # com sorteio para as execuções não voltarem juntas, e relê.
            time.sleep(random.uniform(0, 0.05 * 2 ** min(tentativa, 5)))
            continue
        return resposta
    raise PerdeuADisputa(f"o lembrete {ref.id} mudou em todas as {TENTATIVAS} tentativas")


def complete(reminder_id: str) -> Reminder | None:
    """`None` se o id não existe. Concluir de novo não muda a hora da primeira vez."""
    ref = _ref(reminder_id)
    if ref is None:
        return None
    agora = _agora()

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists:
            return None, False
        if snap.get("completed_at") is not None:
            return None, True
        return {"completed_at": agora, "updated_at": agora}, True

    return get(reminder_id) if _trocar(ref, decidir) else None


def _a_enviar(consulta: Any) -> Any:
    from google.cloud.firestore import FieldFilter

    return consulta.where(filter=FieldFilter("completed_at", "==", None)).where(
        filter=FieldFilter("enviado_em", "==", None)
    )


def vencidos(desde: datetime, ate: datetime) -> list[Reminder]:
    from google.cloud.firestore import FieldFilter

    consulta = (
        _a_enviar(_cliente().collection(COLECAO))
        .where(filter=FieldFilter("due_at", ">=", _instante(desde)))
        .where(filter=FieldFilter("due_at", "<=", _instante(ate)))
        .order_by("due_at")
    )
    return _pela_ordem([_lembrete(s) for s in consulta.stream()])


def atrasados(antes_de: datetime) -> list[Reminder]:
    from google.cloud.firestore import FieldFilter

    consulta = (
        _a_enviar(_cliente().collection(COLECAO))
        .where(filter=FieldFilter("due_at", "<", _instante(antes_de)))
        .order_by("due_at")
    )
    return _pela_ordem([_lembrete(s) for s in consulta.stream()])


def reservar_envio(reminder_id: str, *, por: str, ate: datetime, agora: datetime) -> bool:
    ref = _ref(reminder_id)
    if ref is None:
        return False
    ate, agora = _instante(ate), _instante(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists or snap.get("completed_at") is not None:
            return None, False
        if snap.get("enviado_em") is not None:
            return None, False
        reservado_ate = _lido(snap.get("envio_reservado_ate"))
        if reservado_ate is not None and reservado_ate > agora:
            return None, False
        return {"envio_reservado_por": por, "envio_reservado_ate": ate}, True

    return bool(_trocar(ref, decidir))


def marcar_envio(reminder_id: str, *, por: str, estado: str, agora: datetime) -> bool:
    ref = _ref(reminder_id)
    if ref is None:
        return False
    agora = _instante(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists or snap.get("envio_reservado_por") != por:
            return None, False
        if snap.get("enviado_em") is not None:
            return None, False
        mudanca = {
            "enviado_em": agora,
            "envio_estado": estado,
            "updated_at": agora,
            "envio_reservado_por": None,
            "envio_reservado_ate": None,
        }
        return mudanca, True

    return bool(_trocar(ref, decidir))


def soltar_envio(reminder_id: str, *, por: str) -> None:
    ref = _ref(reminder_id)
    if ref is None:
        return

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
        if snap.exists and snap.get("envio_reservado_por") == por:
            return {"envio_reservado_por": None, "envio_reservado_ate": None}, None
        return None, None

    _trocar(ref, decidir)
