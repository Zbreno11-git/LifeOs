"""A coleção `memoria` do Firestore (Sessão 13, D66): os fatos que o dono contou.

Regras (D48), cada uma com teste em `tests/test_memoria_store.py`:
- **só se acrescenta:** um fato nasce com o texto e nunca o perde; substituir e esquecer mudam só as
  marcas (`ativo`, `invalida_em`, `substituido_por`, `esquecido_em`, `apagar_em`);
- **o filtro está aqui também** (`regras.recusa`): todo caminho que grava (o extrator, o `viking
  memoria --corrigir`, o restaurar do backup) passa por `gravar`/`importar`, e nenhum escapa dele;
- **o substituído fica** (histórico, dá para desfazer); **o esquecido some** em 30 dias, pela TTL do
  Firestore em `apagar_em` (o dono, 2026-10-08), e até lá o `devolver` o traz de volta;
- **a busca por significado** é `find_nearest` com o filtro `ativo == true`: o emulador aceita sem
  índice (medido em 2026-10-08), a produção exige o índice vetorial composto de `INDICES`, que
  `scripts/nuvem.py` cria e a prova do deploy exerce;
- **o id é um UUID**, e o terminal usa os 8 primeiros caracteres (`por_prefixo`);
- nada do texto vai ao log: as exceções dizem o id, nunca o fato.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum, registro_interface
from lifeos.memoria import regras, vetores

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "memoria"
APAGAR_DEPOIS = timedelta(days=30)  # o esquecido some de vez (o dono, 2026-10-08)
ORIGENS = ("chat", "viking memoria", "backup")
PREFIXO_MINIMO = 6
# (coleção, ((campo, ordem), …)): o índice vetorial composto que o `parecidos` pede na produção
# (`ativo` igual e o vetor). `scripts/nuvem.py` cria e confere; "VECTOR:N" é um campo vetorial de N
# dimensões (no `gcloud`, `vector-config={dimension=N,flat}`).
INDICES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (COLECAO, (("ativo", "ASCENDING"), ("vetor", f"VECTOR:{vetores.DIMENSAO}"))),
)
_CAMPOS = (
    "texto",
    "origem",
    "sessao",
    "turno",
    "criado_em",
    "ativo",
    "invalida_em",
    "substituido_por",
    "esquecido_em",
    "apagar_em",
    "vetor",
    "vetor_modelo",
    "vetor_dim",
)
# O que o backup leva (sem o vetor, que se reconstrói do texto; D66).
CAMPOS_DA_COPIA = (
    "id",
    "texto",
    "origem",
    "sessao",
    "turno",
    "criado_em",
    "ativo",
    "invalida_em",
    "substituido_por",
    "esquecido_em",
    "apagar_em",
)
_INSTANTES = ("criado_em", "invalida_em", "esquecido_em", "apagar_em")
CRIADO, IGUAL, DIFERENTE = "criado", "igual", "diferente"


class Recusado(ValueError):
    """O texto não pode virar fato (`regras.recusa`); a mensagem é o motivo, nunca o texto."""


@dataclass(frozen=True)
class Fato:
    id: str
    texto: str
    origem: str
    sessao: str
    turno: str
    criado_em: datetime
    ativo: bool
    invalida_em: datetime | None = None
    substituido_por: str | None = None
    esquecido_em: datetime | None = None
    apagar_em: datetime | None = None
    vetor_modelo: str | None = None
    vetor_dim: int | None = None
    distancia: float | None = None  # só no `parecidos`: 0 é igual, 2 é o oposto (cosseno)

    @property
    def curto(self) -> str:
        return self.id[:8]


def id_valido(texto: object) -> bool:
    try:
        return isinstance(texto, str) and str(uuid.UUID(texto)) == texto
    except ValueError:
        return False


def _colecao() -> Any:
    return firestore_comum.cliente().collection(COLECAO)


def _ref(fato_id: str) -> DocumentReference:
    if not id_valido(fato_id):
        raise ValueError("o id de um fato é um UUID")
    return _colecao().document(fato_id)


def _agora(agora: datetime | None) -> datetime:
    return firestore_comum.instante(agora or datetime.now(UTC))


def _fato(snap: DocumentSnapshot, distancia: float | None = None) -> Fato:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, sem o texto
        raise ValueError(f"fato {snap.id} sem os campos {faltam}")
    criado_em = firestore_comum.lido(dados["criado_em"])
    assert criado_em is not None
    return Fato(
        id=snap.id,
        texto=dados["texto"],
        origem=dados["origem"],
        sessao=dados["sessao"],
        turno=dados["turno"],
        criado_em=criado_em,
        ativo=bool(dados["ativo"]),
        invalida_em=firestore_comum.lido(dados["invalida_em"]),
        substituido_por=dados["substituido_por"],
        esquecido_em=firestore_comum.lido(dados["esquecido_em"]),
        apagar_em=firestore_comum.lido(dados["apagar_em"]),
        vetor_modelo=dados["vetor_modelo"],
        vetor_dim=dados["vetor_dim"],
        distancia=distancia,
    )


def _vetor(vetor: list[float] | None) -> Any:
    if vetor is None:
        return None
    if len(vetor) != vetores.DIMENSAO:
        raise ValueError(f"o vetor de um fato tem {vetores.DIMENSAO} dimensões")
    from google.cloud.firestore_v1.vector import Vector

    return Vector([float(x) for x in vetor])


def obter(fato_id: str) -> Fato | None:
    snap = _ref(fato_id).get()
    return _fato(snap) if snap.exists else None


def gravar(
    texto: str,
    *,
    origem: str,
    vetor: list[float] | None,
    sessao: str = "",
    turno: str = "",
    substitui: str | None = None,
    agora: datetime | None = None,
) -> Fato:
    """Um fato novo (o texto limpo e já filtrado). Com `substitui`, o fato antigo, se ainda está
    ativo, fica marcado como substituído por este; o novo nasce primeiro (falhar no meio deixa os
    dois ativos, nunca nenhum)."""
    motivo = regras.recusa(texto)
    if motivo is not None:
        raise Recusado(motivo)
    if origem not in ORIGENS:
        raise ValueError(f"origem desconhecida: {origem!r}")
    if substitui is not None and not id_valido(substitui):
        raise ValueError("o fato substituído é um UUID")
    momento = _agora(agora)
    fato_id = str(uuid.uuid4())
    documento = dict.fromkeys(_CAMPOS)
    documento.update(
        texto=regras.limpo(texto),
        origem=origem,
        sessao=sessao,
        turno=turno,
        criado_em=momento,
        ativo=True,
        vetor=_vetor(vetor),
        vetor_modelo=vetores.MODELO if vetor is not None else None,
        vetor_dim=vetores.DIMENSAO if vetor is not None else None,
    )
    _ref(fato_id).create(documento)
    if substitui is not None:
        _marcar_substituido(substitui, fato_id, momento)
    fato = obter(fato_id)
    assert fato is not None
    return fato


def _marcar_substituido(antigo: str, novo: str, momento: datetime) -> None:
    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
        dados = snap.to_dict() if snap.exists else None
        if not dados or not dados.get("ativo"):
            return None, None  # já saiu (esquecido ou substituído): nada a marcar
        return {"ativo": False, "invalida_em": momento, "substituido_por": novo}, None

    firestore_comum.trocar(_ref(antigo), decidir)


def esquecer(fato_id: str, agora: datetime | None = None) -> Fato | None:
    """Tira o fato da conversa na hora; o texto some em 30 dias (`apagar_em`, a TTL). `None` se
    o fato não existe."""
    momento = _agora(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists:
            return None, False
        if (snap.to_dict() or {}).get("esquecido_em") is not None:
            return None, True  # já esquecido: o prazo não recomeça
        mudanca = {"ativo": False, "esquecido_em": momento, "apagar_em": momento + APAGAR_DEPOIS}
        return mudanca, True

    if not firestore_comum.trocar(_ref(fato_id), decidir):
        return None
    return obter(fato_id)


def devolver(fato_id: str, agora: datetime | None = None) -> Fato | None:
    """Devolve um fato esquecido (antes de sumir) ou substituído. No substituído, o que entrou no
    lugar dele é esquecido (os dois juntos contradiriam). `None` se não há o que desfazer."""
    momento = _agora(agora)
    atual = obter(fato_id)
    if atual is None:
        return None
    if atual.esquecido_em is not None:
        if atual.apagar_em is not None and atual.apagar_em <= momento:
            return None  # o prazo passou: a TTL vai apagar, e o fato não volta

        def voltar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("esquecido_em") is None:
                return None, None
            vivo = dados.get("invalida_em") is None
            return {"ativo": vivo, "esquecido_em": None, "apagar_em": None}, None

        firestore_comum.trocar(_ref(fato_id), voltar)
        return obter(fato_id)
    if atual.invalida_em is not None:
        substituto = atual.substituido_por

        def reativar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("invalida_em") is None:
                return None, None
            return {"ativo": True, "invalida_em": None, "substituido_por": None}, None

        firestore_comum.trocar(_ref(fato_id), reativar)
        if substituto is not None and id_valido(substituto):
            esquecer(substituto, momento)
        return obter(fato_id)
    return None


def todos() -> list[Fato]:
    """Todos os fatos ainda guardados (os esquecidos até a TTL os apagar), do mais novo ao mais
    velho."""
    return sorted((_fato(s) for s in _colecao().stream()), key=lambda f: f.criado_em, reverse=True)


def ativos() -> list[Fato]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("ativo", "==", True))
    return sorted((_fato(s) for s in consulta.stream()), key=lambda f: f.criado_em, reverse=True)


def parecidos(vetor: list[float], k: int = regras.POR_TURNO) -> list[Fato]:
    """Os `k` fatos ativos mais parecidos com o vetor, do mais perto ao mais longe."""
    from google.cloud.firestore import FieldFilter
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

    consulta = (
        _colecao()
        .where(filter=FieldFilter("ativo", "==", True))
        .find_nearest(
            vector_field="vetor",
            query_vector=_vetor(vetor),
            distance_measure=DistanceMeasure.COSINE,
            limit=k,
            distance_result_field="_distancia",
        )
    )
    achados = [_fato(s, float(s.get("_distancia"))) for s in consulta.get()]
    return sorted(achados, key=lambda f: f.distancia if f.distancia is not None else 2.0)


def ultima_da_sessao(sessao: str) -> Fato | None:
    """A última anotação ativa desta conversa (o "esquece isso")."""
    if not sessao:
        return None
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("sessao", "==", sessao))
    vivos = [f for f in (_fato(s) for s in consulta.stream()) if f.ativo]
    return max(vivos, key=lambda f: f.criado_em) if vivos else None


def criados_entre(inicio: datetime, fim: datetime) -> list[Fato]:
    from google.cloud.firestore import FieldFilter

    consulta = (
        _colecao()
        .where(filter=FieldFilter("criado_em", ">=", firestore_comum.instante(inicio)))
        .where(filter=FieldFilter("criado_em", "<", firestore_comum.instante(fim)))
    )
    return sorted((_fato(s) for s in consulta.stream()), key=lambda f: f.criado_em)


def por_prefixo(prefixo: str) -> str | None:
    """O id completo de um prefixo (o terminal mostra 8 caracteres). `None` se nenhum ou mais de
    um casa: um prefixo ambíguo nunca escolhe."""
    prefixo = (prefixo or "").strip().lower()
    if len(prefixo) < PREFIXO_MINIMO or any(c not in "0123456789abcdef-" for c in prefixo):
        return None
    casam = [s.id for s in _colecao().select([]).stream() if s.id.startswith(prefixo)]
    return casam[0] if len(casam) == 1 else None


def sem_vetor() -> list[Fato]:
    """Os fatos guardados cujo vetor falta ou é de outro modelo ou dimensão (o `--reindexar`)."""
    return [
        f for f in todos() if f.vetor_modelo != vetores.MODELO or f.vetor_dim != vetores.DIMENSAO
    ]


def trocar_vetor(fato_id: str, vetor: list[float]) -> None:
    _ref(fato_id).update(
        {"vetor": _vetor(vetor), "vetor_modelo": vetores.MODELO, "vetor_dim": vetores.DIMENSAO}
    )


# --- o backup (D66: os textos e as marcas, sem o vetor) ----------------------------------------


def _iso(momento: datetime | None) -> str | None:
    """O instante na cópia: o formato do backup (UTC, microssegundos sempre escritos)."""
    return registro_interface.texto_do_instante(momento)


def copia(fato: Fato) -> dict[str, Any]:
    return {
        "id": fato.id,
        "texto": fato.texto,
        "origem": fato.origem,
        "sessao": fato.sessao,
        "turno": fato.turno,
        "criado_em": _iso(fato.criado_em),
        "ativo": fato.ativo,
        "invalida_em": _iso(fato.invalida_em),
        "substituido_por": fato.substituido_por,
        "esquecido_em": _iso(fato.esquecido_em),
        "apagar_em": _iso(fato.apagar_em),
    }


def exportar() -> list[dict[str, Any]]:
    return sorted((copia(f) for f in todos()), key=lambda c: c["id"])


def importar(dados: dict[str, Any]) -> str:
    """A restauração de um backup: o documento com o mesmo id e as mesmas marcas, por `create()`,
    sem vetor (o `--reindexar` refaz). Nunca sobrescreve: existe igual → `igual`; diferente →
    `diferente`, e o da nuvem fica. O texto passa pelo mesmo filtro."""
    from google.api_core.exceptions import AlreadyExists

    motivo = regras.recusa(dados["texto"])
    if motivo is not None:
        raise Recusado(motivo)
    documento = dict.fromkeys(_CAMPOS)
    documento.update({c: dados[c] for c in CAMPOS_DA_COPIA if c != "id"})
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
