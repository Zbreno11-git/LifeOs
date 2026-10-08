"""A coleção `receitas` do Firestore (Sessão 13b, D48 e D67): os procedimentos que o dono ensinou.

Uma receita nasce **proposta** (`estado="proposta"`, fora do `roda`) por quem lê só a mensagem que o
dono digitou (`extrator.py`), e só vira **guardada** quando o dono digita `guarda receita` naquela
conversa (`na_nuvem`, antes do modelo). Ignorada, a proposta some em 1 dia pela TTL de `apagar_em`.

As regras são as dos fatos (`store.py`), cada uma com teste em `tests/test_memoria_receitas.py`:
- **só se acrescenta:** o nome e os passos nunca mudam; guardar, substituir e esquecer mudam marcas;
- **o filtro está aqui também** (`regras.recusa_receita`): propor, guardar e o restaurar do backup;
- **o mesmo nome substitui:** guardar com o nome de uma ativa marca a velha (`invalida_em`,
  `substituido_por`), que fica (dá para desfazer);
- **o esquecido some** em 30 dias, e até lá o `devolver` o traz de volta;
- **coleção própria, sem vetor:** a busca é pelo nome (o dono, 2026-10-08: "pelo nome"), então o
  `parecidos` dos fatos e o índice vetorial não mudam, e nada aqui pede índice composto;
- nada do texto vai ao log: as exceções dizem o id, nunca a receita.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum, registro_interface
from lifeos.memoria import regras

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "receitas"
PROPOSTA_VALE = timedelta(days=1)  # a proposta ignorada morre (o dono, 2026-10-08)
APAGAR_DEPOIS = timedelta(days=30)  # a esquecida some de vez, como o fato
ORIGENS = ("chat", "backup")
PROPOSTA, GUARDADA = "proposta", "guardada"
ESTADOS = (PROPOSTA, GUARDADA)
_CAMPOS = (
    "nome",
    "nome_lido",
    "passos",
    "estado",
    "ativo",
    "origem",
    "sessao",
    "turno",
    "criado_em",
    "guardada_em",
    "invalida_em",
    "substituido_por",
    "esquecido_em",
    "apagar_em",
)
CAMPOS_DA_COPIA = ("id", *(c for c in _CAMPOS if c != "nome_lido"))
_INSTANTES = ("criado_em", "guardada_em", "invalida_em", "esquecido_em", "apagar_em")
CRIADO, IGUAL, DIFERENTE = "criado", "igual", "diferente"


class Recusada(ValueError):
    """A receita não pode existir (`regras.recusa_receita`); a mensagem é o motivo, nunca o texto."""


@dataclass(frozen=True)
class Receita:
    id: str
    nome: str
    passos: tuple[str, ...]
    estado: str
    ativo: bool
    origem: str
    sessao: str
    turno: str
    criado_em: datetime
    guardada_em: datetime | None = None
    invalida_em: datetime | None = None
    substituido_por: str | None = None
    esquecido_em: datetime | None = None
    apagar_em: datetime | None = None

    @property
    def curto(self) -> str:
        return self.id[:8]

    @property
    def nome_lido(self) -> str:
        return regras.nome_lido(self.nome)


def id_valido(texto: object) -> bool:
    try:
        return isinstance(texto, str) and str(uuid.UUID(texto)) == texto
    except ValueError:
        return False


def _colecao() -> Any:
    return firestore_comum.cliente().collection(COLECAO)


def _ref(receita_id: str) -> DocumentReference:
    if not id_valido(receita_id):
        raise ValueError("o id de uma receita é um UUID")
    return _colecao().document(receita_id)


def _agora(agora: datetime | None) -> datetime:
    return firestore_comum.instante(agora or datetime.now(UTC))


def _receita(snap: DocumentSnapshot) -> Receita:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, sem o texto
        raise ValueError(f"receita {snap.id} sem os campos {faltam}")
    criado_em = firestore_comum.lido(dados["criado_em"])
    assert criado_em is not None
    return Receita(
        id=snap.id,
        nome=dados["nome"],
        passos=tuple(dados["passos"]),
        estado=dados["estado"],
        ativo=bool(dados["ativo"]),
        origem=dados["origem"],
        sessao=dados["sessao"],
        turno=dados["turno"],
        criado_em=criado_em,
        guardada_em=firestore_comum.lido(dados["guardada_em"]),
        invalida_em=firestore_comum.lido(dados["invalida_em"]),
        substituido_por=dados["substituido_por"],
        esquecido_em=firestore_comum.lido(dados["esquecido_em"]),
        apagar_em=firestore_comum.lido(dados["apagar_em"]),
    )


def obter(receita_id: str) -> Receita | None:
    snap = _ref(receita_id).get()
    return _receita(snap) if snap.exists else None


def propor(
    nome: str,
    passos: list[str],
    *,
    sessao: str,
    turno: str = "",
    agora: datetime | None = None,
) -> Receita:
    """Uma proposta (fora do `roda` até o `guarda receita`), que morre em 1 dia se ignorada."""
    motivo = regras.recusa_receita(nome, passos)
    if motivo is not None:
        raise Recusada(motivo)
    if not sessao:
        raise ValueError("uma proposta é de uma conversa")
    momento = _agora(agora)
    receita_id = str(uuid.uuid4())
    documento = dict.fromkeys(_CAMPOS)
    documento.update(
        nome=regras.limpo(nome),
        nome_lido=regras.nome_lido(nome),
        passos=[regras.limpo(p) for p in passos],
        estado=PROPOSTA,
        ativo=False,
        origem="chat",
        sessao=sessao,
        turno=turno,
        criado_em=momento,
        apagar_em=momento + PROPOSTA_VALE,
    )
    _ref(receita_id).create(documento)
    receita = obter(receita_id)
    assert receita is not None
    return receita


def _proposta_da_sessao(sessao: str, momento: datetime) -> Receita | None:
    """A última proposta viva desta conversa (o `guarda receita` só pega ela)."""
    if not sessao:
        return None
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("sessao", "==", sessao))
    vivas = [
        r
        for r in (_receita(s) for s in consulta.stream())
        if r.estado == PROPOSTA and r.apagar_em is not None and r.apagar_em > momento
    ]
    return max(vivas, key=lambda r: r.criado_em) if vivas else None


def guardar(sessao: str, agora: datetime | None = None) -> tuple[Receita, Receita | None] | None:
    """O `guarda receita`: a última proposta viva desta conversa vira guardada. Devolve (a
    guardada, a que ela substituiu, se havia uma ativa com o mesmo nome), ou `None` se não há
    proposta para guardar."""
    momento = _agora(agora)
    proposta = _proposta_da_sessao(sessao, momento)
    if proposta is None:
        return None
    motivo = regras.recusa_receita(proposta.nome, list(proposta.passos))
    if motivo is not None:  # o filtro de hoje recusa uma proposta de antes: não guarda
        raise Recusada(motivo)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        dados = snap.to_dict() if snap.exists else None
        if not dados or dados.get("estado") != PROPOSTA:
            return None, False  # outro `guarda receita` chegou antes
        return {"estado": GUARDADA, "ativo": True, "guardada_em": momento, "apagar_em": None}, True

    if not firestore_comum.trocar(_ref(proposta.id), decidir):
        return None
    antigas = [r for r in ativas() if r.nome_lido == proposta.nome_lido and r.id != proposta.id]
    for antiga in antigas:
        _marcar_substituida(antiga.id, proposta.id, momento)
    guardada = obter(proposta.id)
    assert guardada is not None
    return guardada, (antigas[0] if antigas else None)


def _marcar_substituida(antiga: str, nova: str, momento: datetime) -> None:
    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
        dados = snap.to_dict() if snap.exists else None
        if not dados or not dados.get("ativo"):
            return None, None
        return {"ativo": False, "invalida_em": momento, "substituido_por": nova}, None

    firestore_comum.trocar(_ref(antiga), decidir)


def esquecer(receita_id: str, agora: datetime | None = None) -> Receita | None:
    """Tira a receita do `roda` na hora; o texto some em 30 dias. `None` se não existe."""
    momento = _agora(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists:
            return None, False
        if (snap.to_dict() or {}).get("esquecido_em") is not None:
            return None, True  # já esquecida: o prazo não recomeça
        mudanca = {"ativo": False, "esquecido_em": momento, "apagar_em": momento + APAGAR_DEPOIS}
        return mudanca, True

    if not firestore_comum.trocar(_ref(receita_id), decidir):
        return None
    return obter(receita_id)


def devolver(receita_id: str, agora: datetime | None = None) -> Receita | None:
    """Devolve uma guardada esquecida (antes de sumir) ou substituída; na substituída, a que entrou
    no lugar é esquecida (duas com o mesmo nome não rodam). `None` se não há o que desfazer (uma
    proposta não se devolve: o dono a ensina de novo)."""
    momento = _agora(agora)
    atual = obter(receita_id)
    if atual is None or atual.estado != GUARDADA:
        return None
    if atual.esquecido_em is not None:
        if atual.apagar_em is not None and atual.apagar_em <= momento:
            return None

        def voltar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("esquecido_em") is None:
                return None, None
            viva = dados.get("invalida_em") is None
            return {"ativo": viva, "esquecido_em": None, "apagar_em": None}, None

        firestore_comum.trocar(_ref(receita_id), voltar)
        devolvida = obter(receita_id)
        if devolvida is not None and devolvida.ativo:
            _esquecer_xaras(devolvida, momento)
        return devolvida
    if atual.invalida_em is not None:
        substituta = atual.substituido_por

        def reativar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("invalida_em") is None:
                return None, None
            return {"ativo": True, "invalida_em": None, "substituido_por": None}, None

        firestore_comum.trocar(_ref(receita_id), reativar)
        if substituta is not None and id_valido(substituta):
            esquecer(substituta, momento)
        return obter(receita_id)
    return None


def _esquecer_xaras(receita: Receita, momento: datetime) -> None:
    """Uma esquecida que volta e encontra outra ativa com o mesmo nome: a outra é esquecida (o
    `roda` nunca escolhe entre duas iguais)."""
    for outra in ativas():
        if outra.id != receita.id and outra.nome_lido == receita.nome_lido:
            esquecer(outra.id, momento)


def todas() -> list[Receita]:
    """Todas as guardadas e propostas ainda no banco, da mais nova à mais velha."""
    return sorted(
        (_receita(s) for s in _colecao().stream()), key=lambda r: r.criado_em, reverse=True
    )


def ativas() -> list[Receita]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("ativo", "==", True))
    return sorted((_receita(s) for s in consulta.stream()), key=lambda r: r.nome_lido)


def por_nome(texto: str) -> list[Receita]:
    """As ativas que o `roda TEXTO` pode querer dizer: a de nome igual, se houver; senão, as que
    começam com o texto. Mais de uma é ambíguo: quem chama nunca escolhe."""
    lido = regras.nome_lido(texto)
    if not lido:
        return []
    candidatas = ativas()
    iguais = [r for r in candidatas if r.nome_lido == lido]
    if iguais:
        return iguais
    return [r for r in candidatas if r.nome_lido.startswith(lido)]


def da_semana(inicio: datetime, fim: datetime) -> list[Receita]:
    """As guardadas ou esquecidas entre `inicio` e `fim` (o resumo de segunda); as propostas
    ignoradas não entram."""
    inicio, fim = firestore_comum.instante(inicio), firestore_comum.instante(fim)

    def dentro(momento: datetime | None) -> bool:
        return momento is not None and inicio <= momento < fim

    escolhidas = [
        r
        for r in todas()
        if r.estado == GUARDADA and (dentro(r.guardada_em) or dentro(r.esquecido_em))
    ]
    return sorted(escolhidas, key=lambda r: r.guardada_em or r.criado_em)


def por_prefixo(prefixo: str, minimo: int = 6) -> str | None:
    """O id completo de um prefixo; `None` se nenhum ou mais de um casa."""
    prefixo = (prefixo or "").strip().lower()
    if len(prefixo) < minimo or any(c not in "0123456789abcdef-" for c in prefixo):
        return None
    casam = [s.id for s in _colecao().select([]).stream() if s.id.startswith(prefixo)]
    return casam[0] if len(casam) == 1 else None


# --- o backup (D67: a coleção inteira, todos os estados) ---------------------------------------


def _iso(momento: datetime | None) -> str | None:
    return registro_interface.texto_do_instante(momento)


def copia(receita: Receita) -> dict[str, Any]:
    return {
        "id": receita.id,
        "nome": receita.nome,
        "passos": list(receita.passos),
        "estado": receita.estado,
        "ativo": receita.ativo,
        "origem": receita.origem,
        "sessao": receita.sessao,
        "turno": receita.turno,
        "criado_em": _iso(receita.criado_em),
        "guardada_em": _iso(receita.guardada_em),
        "invalida_em": _iso(receita.invalida_em),
        "substituido_por": receita.substituido_por,
        "esquecido_em": _iso(receita.esquecido_em),
        "apagar_em": _iso(receita.apagar_em),
    }


def exportar() -> list[dict[str, Any]]:
    return sorted((copia(r) for r in todas()), key=lambda c: c["id"])


def importar(dados: dict[str, Any]) -> str:
    """A restauração de um backup: o mesmo id e as mesmas marcas, por `create()`. Nunca
    sobrescreve: igual → `igual`; diferente → `diferente`, e a da nuvem fica."""
    from google.api_core.exceptions import AlreadyExists

    motivo = regras.recusa_receita(dados["nome"], dados["passos"])
    if motivo is not None:
        raise Recusada(motivo)
    documento = dict.fromkeys(_CAMPOS)
    documento.update({c: dados[c] for c in CAMPOS_DA_COPIA if c != "id"})
    documento["nome_lido"] = regras.nome_lido(dados["nome"])
    for campo in _INSTANTES:
        texto = dados[campo]
        documento[campo] = (
            firestore_comum.instante(datetime.fromisoformat(texto)) if texto else None
        )
    ref = _ref(dados["id"])
    try:
        ref.create(documento)
    except AlreadyExists:
        atual = obter(dados["id"])
        return IGUAL if atual is not None and copia(atual) == dados else DIFERENTE
    return CRIADO
