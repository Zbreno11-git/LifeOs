"""As confirmações no Firestore (Sessão 10c, D60): a implementação da nuvem de
`confirmacao_interface.Confirmacoes`, que passa o mesmo contrato do SQLite
(`tests/test_confirmacao.py`, no emulador). A regra mora em `confirmacao.py`.

Onde o Firestore difere do SQLite, e o que fazemos:
- **não há transação que valha** (medido na Sessão 10: trava com execuções juntas), então:
  - **o código tem um dono só por construção**: cada número tem um documento
    `codigos/NNNN` com `reservado_ate`. Quem o cria (`create()`, que falha se já existe) fica com
    ele; se ele existe e a reserva venceu, a troca é por comparar e trocar
    (`firestore_comum.trocar`). Duas instâncias sorteando o mesmo número não vencem as duas;
  - **gastar uma vez só** por comparar e trocar no documento da proposta. Antes, a reserva do
    código se estende para a janela de uso (o passo que consome vai por último: se ele falhar,
    sobra só uma reserva mais longa, que é inofensiva);
- **não há contador**: o id é o relógio em nanossegundos, gravado com `create()` (como o registro);
- **consultas de um campo só** (`acao`, `codigo`, `reservado_ate`), e o resto filtrado aqui:
  nenhum índice composto. O volume é pequeno: a TTL em `apagar_em` apaga a proposta com 30 dias
  (acima dos 8 da unicidade e dos 7 do desfazer), e há no máximo 10 mil documentos de código;
- **todo documento inteiro**, e um documento parcial erra alto na leitura.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum
from lifeos.confirmacao_interface import (
    ABERTA,
    CONSUMIDA,
    SUBSTITUIDA,
    ErroConfirmacao,
    Linha,
    Proposta,
)

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "confirmacoes"
CODIGOS = "codigos"
# Quanto depois de nascer a TTL pode apagar a proposta (`scripts/nuvem.py`, passo `ttl`).
VIDA = timedelta(days=30)
SORTEIOS = 1000  # com no máximo metade dos números reservados, 1000 sorteios não se esgotam
_CAMPOS = (
    "id",
    "acao",
    "codigo",
    "dados",
    "estado",
    "criada_em",
    "expira_em",
    "consumida_em",
    "resultado",
    "erros",
    "apagar_em",
)


def _colecao() -> Any:
    return firestore_comum.cliente().collection(COLECAO)


def _ref(proposta_id: int) -> DocumentReference:
    return _colecao().document(str(int(proposta_id)))


def _codigo_ref(codigo: str) -> DocumentReference:
    return firestore_comum.cliente().collection(CODIGOS).document(codigo)


def _linha(snap: DocumentSnapshot) -> Linha:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, não lê pela metade
        raise ValueError(f"confirmação {snap.id} sem os campos {faltam}")
    criada_em = firestore_comum.lido(dados["criada_em"])
    expira_em = firestore_comum.lido(dados["expira_em"])
    assert criada_em is not None and expira_em is not None
    return Linha(
        id=int(dados["id"]),
        acao=dados["acao"],
        codigo=dados["codigo"],
        dados=json.loads(dados["dados"]),
        estado=dados["estado"],
        criada_em=criada_em,
        expira_em=expira_em,
        consumida_em=firestore_comum.lido(dados["consumida_em"]),
        resultado=json.loads(dados["resultado"]) if dados["resultado"] else {},
        erros=int(dados["erros"]),
    )


def _da_acao(acao: str) -> list[Linha]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("acao", "==", acao))
    return sorted(map(_linha, consulta.stream()), key=lambda linha: linha.id)


def _do_codigo(codigo: str) -> list[Linha]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("codigo", "==", codigo))
    return sorted(map(_linha, consulta.stream()), key=lambda linha: linha.id)


def _reservados(agora: datetime) -> int:
    from google.cloud.firestore import FieldFilter

    # `Any`: os tipos da biblioteca (2.x) não descrevem `count().get()`; medido no emulador.
    consulta: Any = (
        firestore_comum.cliente()
        .collection(CODIGOS)
        .where(filter=FieldFilter("reservado_ate", ">=", agora))
    )
    resultado = consulta.count().get()
    return int(resultado[0][0].value)


def _reservar(codigo: str, *, ate: datetime, agora: datetime) -> bool:
    """Fica com o número se ninguém o reserva agora: `create()` se é a primeira vez; senão, troca
    só uma reserva vencida."""
    from google.api_core.exceptions import AlreadyExists

    ref = _codigo_ref(codigo)
    try:
        ref.create({"codigo": codigo, "reservado_ate": ate})
    except AlreadyExists:
        pass
    else:
        return True

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        atual = firestore_comum.lido(snap.get("reservado_ate")) if snap.exists else None
        if atual is not None and atual >= agora:
            return None, False
        return {"reservado_ate": ate}, True

    return bool(firestore_comum.trocar(ref, decidir))


def propor(
    acao: str,
    dados: dict[str, Any],
    *,
    criada_em: datetime,
    expira_em: datetime,
    substituir: bool,
    janela_unica: timedelta,
    sortear: Callable[[], str],
    maximo: int,
) -> Proposta:
    from google.api_core.exceptions import AlreadyExists

    del janela_unica  # a janela entra na reserva quando a proposta é gasta (`consumir`)
    criada_em = firestore_comum.instante(criada_em)
    expira_em = firestore_comum.instante(expira_em)
    if substituir:
        cancelar(acao)
    if _reservados(criada_em) >= maximo:
        raise ErroConfirmacao("códigos demais em uso; tente mais tarde")
    for _ in range(SORTEIOS):
        codigo = sortear()
        if _reservar(codigo, ate=expira_em, agora=criada_em):
            break
    else:
        raise ErroConfirmacao("códigos demais em uso; tente mais tarde")
    proposta_id = time.time_ns()
    for _ in range(100):
        documento = dict.fromkeys(_CAMPOS)
        documento.update(
            id=proposta_id,
            acao=acao,
            codigo=codigo,
            dados=json.dumps(dados),
            estado=ABERTA,
            criada_em=criada_em,
            expira_em=expira_em,
            erros=0,
            apagar_em=criada_em + VIDA,
        )
        try:
            _ref(proposta_id).create(documento)
        except AlreadyExists:
            proposta_id = max(proposta_id + 1, time.time_ns())  # outra nasceu no mesmo instante
            continue
        return Proposta(proposta_id, acao, codigo, dados, expira_em)
    raise RuntimeError("não achei um id livre para a proposta em 100 tentativas")


def abertas(acao: str, *, agora: datetime) -> list[Proposta]:
    agora = firestore_comum.instante(agora)
    return [
        Proposta(linha.id, linha.acao, linha.codigo, linha.dados, linha.expira_em)
        for linha in _da_acao(acao)
        if linha.estado == ABERTA and linha.expira_em >= agora
    ]


def mais_recente(acao: str, codigo: str) -> Linha | None:
    linhas = [linha for linha in _do_codigo(codigo) if linha.acao == acao]
    return linhas[-1] if linhas else None


def mais_recente_do_codigo(codigo: str) -> Linha | None:
    linhas = _do_codigo(codigo)
    return linhas[-1] if linhas else None


def criadas_desde(acao: str, desde: datetime) -> int:
    corte = firestore_comum.instante(desde)
    return sum(1 for linha in _da_acao(acao) if linha.criada_em >= corte)


def _mudar_abertas(acao: str, mudar: Callable[[DocumentSnapshot], dict[str, Any] | None]) -> None:
    """Aplica `mudar` a cada proposta ainda aberta da ação, por comparar e trocar."""
    for linha in _da_acao(acao):
        if linha.estado != ABERTA:
            continue

        def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            if not snap.exists or snap.get("estado") != ABERTA:
                return None, None
            return mudar(snap), None

        firestore_comum.trocar(_ref(linha.id), decidir)


def cancelar(acao: str) -> None:
    _mudar_abertas(acao, lambda _snap: {"estado": SUBSTITUIDA})


def consumir(proposta_id: int, *, agora: datetime, reservar_ate: datetime) -> Linha | None:
    agora = firestore_comum.instante(agora)
    ref = _ref(proposta_id)
    snap = ref.get()
    if not snap.exists or snap.get("estado") != ABERTA:
        return None
    # Primeiro a reserva (o código não volta a ser sorteado na janela de uso); por último o gasto.
    _codigo_ref(snap.get("codigo")).set(
        {"codigo": snap.get("codigo"), "reservado_ate": firestore_comum.instante(reservar_ate)}
    )

    def decidir(atual: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not atual.exists or atual.get("estado") != ABERTA:
            return None, False
        return {"estado": CONSUMIDA, "consumida_em": agora}, True

    if not firestore_comum.trocar(ref, decidir):
        return None
    return _linha(ref.get())


def registrar(proposta_id: int, resultado: dict[str, Any]) -> None:
    _ref(proposta_id).update({"resultado": json.dumps(resultado)})


def errar(acao: str, *, agora: datetime, limite: int) -> int | None:
    agora = firestore_comum.instante(agora)
    contagens: list[int] = []
    for linha in _da_acao(acao):
        if linha.estado != ABERTA or linha.expira_em < agora:
            continue

        def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, int | None]:
            if not snap.exists or snap.get("estado") != ABERTA:
                return None, None
            erros = int(snap.get("erros")) + 1
            mudanca: dict[str, Any] = {"erros": erros}
            if erros >= limite:
                mudanca["estado"] = SUBSTITUIDA
            return mudanca, erros

        erros = firestore_comum.trocar(_ref(linha.id), decidir)
        if erros is not None:
            contagens.append(erros)
    if not contagens:
        return None
    return max(limite - max(contagens), 0)
