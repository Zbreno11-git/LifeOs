"""A fila das mãos no Firestore (Sessão 11, D61): a coleção `tarefas`, do lado da nuvem.

Estados: `pendente` → `pega` → `feita`, ou `pendente` → `vencida` (ninguém pegou a tempo). Cada
passagem é por comparar e trocar (`firestore_comum.trocar`), como os lembretes: duas instâncias
do `viking maos` não pegam a mesma tarefa, e o turno não vence uma tarefa que acabou de ser pega.

- **o id é um UUID** gerado aqui, gravado por `create()`;
- **todo documento inteiro** (`None` explícito), e um parcial erra alto na leitura;
- **consulta de um campo só** (`estado == pendente`), com o resto filtrado aqui: nenhum índice
  composto (o emulador não exige e a produção exigiria);
- **o resultado é o texto da página, já redigido no Mac**: o turno o lê e apaga o documento, e a
  TTL em `apagar_em` (1 dia) leva o que sobrar (uma tarefa que o turno desistiu de esperar).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum
from lifeos.maos import fila

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "tarefas"
_CAMPOS = (
    "url",
    "objetivo",
    "manter_aberta",
    "limite_s",
    "estado",
    "criada_em",
    "pegar_ate",
    "pega_por",
    "pega_em",
    "resultado",
    "apagar_em",
)


@dataclass(frozen=True)
class Situacao:
    estado: str
    pega_em: datetime | None
    resultado: str | None


def _ref(tarefa_id: str) -> DocumentReference:
    if not fila.id_valido(tarefa_id):
        raise ValueError("o id da tarefa tem de ser um UUID")
    return firestore_comum.cliente().collection(COLECAO).document(tarefa_id)


def _dados(snap: DocumentSnapshot) -> dict[str, Any]:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, não lê pela metade
        raise ValueError(f"tarefa {snap.id} sem os campos {faltam}")
    return dados


def _instante(snap: DocumentSnapshot, campo: str) -> datetime:
    momento = firestore_comum.lido(_dados(snap)[campo])
    if momento is None:  # os prazos nascem preenchidos: vazio é documento torto
        raise ValueError(f"tarefa {snap.id} sem {campo}")
    return momento


def _tarefa(snap: DocumentSnapshot) -> fila.Tarefa:
    dados = _dados(snap)
    return fila.validar_tarefa(
        {
            "id": snap.id,
            "url": dados["url"],
            "objetivo": dados["objetivo"],
            "manter_aberta": dados["manter_aberta"],
            "limite_s": dados["limite_s"],
        }
    )


def criar(url: str, objetivo: str, *, manter_aberta: bool, limite_s: float, agora: datetime) -> str:
    """Põe a tarefa na fila; devolve o id. O formato é conferido antes de gravar."""
    tarefa_id = str(uuid.uuid4())
    fila.validar_tarefa(
        {
            "id": tarefa_id,
            "url": url,
            "objetivo": objetivo,
            "manter_aberta": manter_aberta,
            "limite_s": limite_s,
        }
    )
    agora = firestore_comum.instante(agora)
    documento = dict.fromkeys(_CAMPOS)
    documento.update(
        url=url,
        objetivo=objetivo,
        manter_aberta=manter_aberta,
        limite_s=float(limite_s),
        estado=fila.PENDENTE,
        criada_em=agora,
        pegar_ate=agora + fila.PEGAR_EM,
        apagar_em=agora + fila.VIDA,
    )
    _ref(tarefa_id).create(documento)
    return tarefa_id


def _depois_de_ler(candidatas: list[DocumentSnapshot]) -> list[DocumentSnapshot]:
    """Nada: é o ponto onde o teste de corrida segura todas as execuções depois da leitura e
    antes da escrita (sem ele, a corrida passaria por acaso: erros, classe 4)."""
    return candidatas


def pegar(por: Any, *, agora: datetime) -> fila.Tarefa | None:
    """A tarefa pendente mais antiga que ainda não venceu, agora de `por`; `None` se não há.
    Só um ganha cada tarefa: quem perde a troca tenta a seguinte."""
    from google.cloud.firestore import FieldFilter

    por = fila.validar_por(por)
    agora = firestore_comum.instante(agora)
    consulta = (
        firestore_comum.cliente()
        .collection(COLECAO)
        .where(filter=FieldFilter("estado", "==", fila.PENDENTE))
    )
    candidatas = sorted(
        (s for s in consulta.stream() if _instante(s, "pegar_ate") >= agora),
        key=lambda s: _instante(s, "criada_em"),
    )
    for snap in _depois_de_ler(candidatas):

        def decidir(atual: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
            # `pegar_ate` não muda depois de criada: o filtro da leitura basta; aqui, só o estado.
            if not atual.exists or atual.get("estado") != fila.PENDENTE:
                return None, False
            return {"estado": fila.PEGA, "pega_por": por, "pega_em": agora}, True

        if firestore_comum.trocar(_ref(snap.id), decidir):
            return _tarefa(snap)
    return None


def entregar(tarefa_id: str, por: Any, resultado: str) -> bool:
    """O resultado de quem pegou; `False` se a tarefa não é dele (ou não está mais pega)."""
    por = fila.validar_por(por)
    texto = fila.resultado_curto(str(resultado))

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists or snap.get("estado") != fila.PEGA or snap.get("pega_por") != por:
            return None, False
        return {"estado": fila.FEITA, "resultado": texto}, True

    return bool(firestore_comum.trocar(_ref(tarefa_id), decidir))


def vencer(tarefa_id: str) -> bool:
    """Ninguém pegou a tempo: a tarefa vence e não roda mais. `False` se já foi pega."""

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists or snap.get("estado") != fila.PENDENTE:
            return None, False
        return {"estado": fila.VENCIDA}, True

    return bool(firestore_comum.trocar(_ref(tarefa_id), decidir))


def situacao(tarefa_id: str) -> Situacao | None:
    snap = _ref(tarefa_id).get()
    if not snap.exists:
        return None
    dados = _dados(snap)
    return Situacao(dados["estado"], firestore_comum.lido(dados["pega_em"]), dados["resultado"])


def apagar(tarefa_id: str) -> None:
    _ref(tarefa_id).delete()
