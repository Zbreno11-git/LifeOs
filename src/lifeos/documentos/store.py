"""As coleções `documentos` e `trechos` do Firestore (Sessão 14, D68): os arquivos que o dono mandou
e os pedaços deles, com o vetor, que a consulta do chat da nuvem acha por tema.

Regras, cada uma com teste em `tests/test_documentos_store.py`:
- **só se acrescenta:** o texto de um trecho nunca muda; aprender, substituir, esquecer e devolver
  mudam marcas (`ativo`, `estado`, `invalida_em`, `substituido_por`, `esquecido_em`, `apagar_em`);
- **aprender em duas fases:** o documento e os trechos nascem fora da busca (`ativo=false`), com
  `apagar_em` de 1 dia; só depois de todo trecho gravado com o vetor eles entram, e o documento por
  último. Cair no meio (o prazo, o teto, o Gemini) deixa nada na busca, e a TTL limpa;
- **a consulta confere o documento de cada trecho achado:** um trecho cujo documento não está ativo
  não volta, mesmo que a marca do trecho tenha ficado para trás (uma ativação com mais de um lote
  que caiu no meio, ou um esquecer que caiu antes de marcar os trechos);
- **o mesmo arquivo no mesmo tema substitui** (o dono, 2026-10-09): o velho fica marcado
  (`substituido_por`), fora da busca, e dá para desfazer;
- **o esquecido some** em 30 dias pela TTL de `apagar_em` (nas duas coleções), e até lá o
  `devolver` o traz de volta;
- **a busca é `find_nearest` com `tema_lido` e `ativo`:** o emulador não pede índice; a produção
  pede o composto de `INDICES`, que `scripts/nuvem.py` cria e a prova do deploy exerce;
- nada do texto vai ao log: as exceções dizem ids e contagens, nunca o trecho.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import firestore_comum, registro_interface
from lifeos.documentos import cortes
from lifeos.memoria import regras, vetores

if TYPE_CHECKING:
    from google.cloud.firestore import DocumentReference, DocumentSnapshot

COLECAO = "documentos"
TRECHOS = "trechos"
APRENDER_VALE = timedelta(days=1)  # um aprender que caiu no meio some pela TTL
APAGAR_DEPOIS = timedelta(days=30)  # o esquecido some de vez, como o fato (o dono, 2026-10-09)
ORIGENS = ("viking documentos", "backup")
APRENDENDO, APRENDIDO = "aprendendo", "aprendido"
ESTADOS = (APRENDENDO, APRENDIDO)
POR_CONSULTA = 5  # trechos por consulta (o dono, 2026-10-09)
LOTE_EMBUTIR = 20  # textos por pedido de embedding (o mesmo da memória)
LOTE_GRAVAR = 200  # documentos por escrita em lote: ~7 KB cada, longe dos 10 MiB do pedido
PREFIXO_MINIMO = 6
# O índice vetorial composto da consulta (o tema e o `ativo` iguais, e o vetor).
INDICES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        TRECHOS,
        (
            ("tema_lido", "ASCENDING"),
            ("ativo", "ASCENDING"),
            ("vetor", f"VECTOR:{vetores.DIMENSAO}"),
        ),
    ),
)
_CAMPOS = (
    "nome",
    "nome_lido",
    "tema",
    "tema_lido",
    "bytes",
    "n_trechos",
    "impressao",
    "origem",
    "estado",
    "ativo",
    "criado_em",
    "aprendido_em",
    "invalida_em",
    "substituido_por",
    "esquecido_em",
    "apagar_em",
)
_CAMPOS_DO_TRECHO = (
    "documento",
    "arquivo",
    "tema_lido",
    "ordem",
    "linha_de",
    "linha_ate",
    "secao",
    "texto",
    "ativo",
    "apagar_em",
    "vetor",
    "vetor_modelo",
    "vetor_dim",
)
CAMPOS_DA_COPIA = ("id", *(c for c in _CAMPOS if c not in ("nome_lido", "tema_lido")))
CAMPOS_DA_COPIA_DO_TRECHO = (
    "id",
    *(c for c in _CAMPOS_DO_TRECHO if c not in ("vetor", "vetor_modelo", "vetor_dim")),
)
_INSTANTES = ("criado_em", "aprendido_em", "invalida_em", "esquecido_em", "apagar_em")
MAX_TEXTO_DO_TRECHO = 4 * cortes.MAX_TRECHO  # o que um backup pode trazer (o corte de hoje é menor)
CRIADO, IGUAL, DIFERENTE = "criado", "igual", "diferente"
Recusado = cortes.Recusado


@dataclass(frozen=True)
class Documento:
    id: str
    nome: str
    tema: str
    bytes: int
    n_trechos: int
    impressao: str
    origem: str
    estado: str
    ativo: bool
    criado_em: datetime
    aprendido_em: datetime | None = None
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

    @property
    def tema_lido(self) -> str:
        return regras.nome_lido(self.tema)


@dataclass(frozen=True)
class Trecho:
    id: str
    documento: str
    arquivo: str
    tema_lido: str
    ordem: int
    linha_de: int
    linha_ate: int
    secao: str
    texto: str
    ativo: bool
    apagar_em: datetime | None = None
    vetor_modelo: str | None = None
    vetor_dim: int | None = None
    distancia: float | None = None  # só na consulta: 0 é igual, 2 é o oposto (cosseno)


def id_valido(texto: object) -> bool:
    try:
        return isinstance(texto, str) and str(uuid.UUID(texto)) == texto
    except ValueError:
        return False


def _colecao() -> Any:
    return firestore_comum.cliente().collection(COLECAO)


def _trechos() -> Any:
    return firestore_comum.cliente().collection(TRECHOS)


def _ref(documento_id: str) -> DocumentReference:
    if not id_valido(documento_id):
        raise ValueError("o id de um documento é um UUID")
    return _colecao().document(documento_id)


def _ref_do_trecho(trecho_id: str) -> DocumentReference:
    if not id_valido(trecho_id):
        raise ValueError("o id de um trecho é um UUID")
    return _trechos().document(trecho_id)


def _agora(agora: datetime | None) -> datetime:
    return firestore_comum.instante(agora or datetime.now(UTC))


def _documento(snap: DocumentSnapshot) -> Documento:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS if c not in dados]
    if faltam:  # um documento parcial não deveria existir: erra alto, sem o texto
        raise ValueError(f"documento {snap.id} sem os campos {faltam}")
    criado_em = firestore_comum.lido(dados["criado_em"])
    assert criado_em is not None
    return Documento(
        id=snap.id,
        nome=dados["nome"],
        tema=dados["tema"],
        bytes=int(dados["bytes"]),
        n_trechos=int(dados["n_trechos"]),
        impressao=dados["impressao"],
        origem=dados["origem"],
        estado=dados["estado"],
        ativo=bool(dados["ativo"]),
        criado_em=criado_em,
        aprendido_em=firestore_comum.lido(dados["aprendido_em"]),
        invalida_em=firestore_comum.lido(dados["invalida_em"]),
        substituido_por=dados["substituido_por"],
        esquecido_em=firestore_comum.lido(dados["esquecido_em"]),
        apagar_em=firestore_comum.lido(dados["apagar_em"]),
    )


def _trecho(snap: DocumentSnapshot, distancia: float | None = None) -> Trecho:
    dados = snap.to_dict() or {}
    faltam = [c for c in _CAMPOS_DO_TRECHO if c not in dados]
    if faltam:
        raise ValueError(f"trecho {snap.id} sem os campos {faltam}")
    return Trecho(
        id=snap.id,
        documento=dados["documento"],
        arquivo=dados["arquivo"],
        tema_lido=dados["tema_lido"],
        ordem=int(dados["ordem"]),
        linha_de=int(dados["linha_de"]),
        linha_ate=int(dados["linha_ate"]),
        secao=dados["secao"],
        texto=dados["texto"],
        ativo=bool(dados["ativo"]),
        apagar_em=firestore_comum.lido(dados["apagar_em"]),
        vetor_modelo=dados["vetor_modelo"],
        vetor_dim=dados["vetor_dim"],
        distancia=distancia,
    )


def _vetor(vetor: list[float] | None) -> Any:
    if vetor is None:
        return None
    if len(vetor) != vetores.DIMENSAO:
        raise ValueError(f"o vetor de um trecho tem {vetores.DIMENSAO} dimensões")
    from google.cloud.firestore_v1.vector import Vector

    return Vector([float(x) for x in vetor])


def texto_do_vetor(arquivo: str, secao: str, texto: str) -> str:
    """O que se embute de um trecho: o título como a página de embeddings recomenda ("title: … |
    text: …"), com o arquivo e o caminho dos títulos (medido no C1: o trecho certo fica mais perto)."""
    titulo = f"{arquivo} — {secao}" if secao else arquivo
    return f"title: {titulo} | text: {texto}"


def obter(documento_id: str) -> Documento | None:
    snap = _ref(documento_id).get()
    return _documento(snap) if snap.exists else None


def _gravar_em_lotes(mudancas: list[tuple[DocumentReference, dict[str, Any], bool]]) -> None:
    """(a referência, os campos, se cria) em escritas de até `LOTE_GRAVAR` documentos."""
    cliente = firestore_comum.cliente()
    for i in range(0, len(mudancas), LOTE_GRAVAR):
        lote = cliente.batch()
        for ref, campos, cria in mudancas[i : i + LOTE_GRAVAR]:
            if cria:
                lote.create(ref, campos)
            else:
                lote.update(ref, campos)
        lote.commit()


def _ids_dos_trechos(documento_id: str) -> list[str]:
    from google.cloud.firestore import FieldFilter

    consulta = _trechos().where(filter=FieldFilter("documento", "==", documento_id)).select([])
    return [s.id for s in consulta.stream()]


def _marcar_trechos(documento_id: str, mudanca: dict[str, Any]) -> None:
    _gravar_em_lotes([(_ref_do_trecho(t), mudanca, False) for t in _ids_dos_trechos(documento_id)])


def aprender(
    nome: str,
    tema: str,
    texto: str,
    *,
    embutir: Callable[[list[str]], list[list[float]]],
    antes_do_lote: Callable[[], None] = lambda: None,
    origem: str = "viking documentos",
    agora: datetime | None = None,
) -> tuple[Documento, Documento | None]:
    """Corta, embute e guarda um arquivo. Devolve (o novo, o que ele substituiu, se havia um ativo
    com o mesmo nome no mesmo tema). `embutir` recebe os textos e devolve um vetor por texto (o
    serviço passa o cliente instrumentado); `antes_do_lote` confere o prazo antes de cada pedido."""
    nome, tema, texto = cortes.nome_valido(nome), cortes.tema_valido(tema), cortes.conferir(texto)
    if origem not in ORIGENS:
        raise ValueError(f"origem desconhecida: {origem!r}")
    pedacos = cortes.cortar(texto)
    if not pedacos:
        raise Recusado("o arquivo não tem texto (só títulos ou espaços)")
    momento = _agora(agora)
    documento_id = str(uuid.uuid4())
    tema_lido = regras.nome_lido(tema)
    documento = dict.fromkeys(_CAMPOS)
    documento.update(
        nome=nome,
        nome_lido=regras.nome_lido(nome),
        tema=tema,
        tema_lido=tema_lido,
        bytes=len(texto.encode("utf-8")),
        n_trechos=len(pedacos),
        impressao=hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        origem=origem,
        estado=APRENDENDO,
        ativo=False,
        criado_em=momento,
        apagar_em=momento + APRENDER_VALE,
    )
    _ref(documento_id).create(documento)
    ids: list[str] = []
    for i in range(0, len(pedacos), LOTE_EMBUTIR):
        lote = pedacos[i : i + LOTE_EMBUTIR]
        antes_do_lote()
        vetores_ = embutir([texto_do_vetor(nome, p.secao, p.texto) for p in lote])
        if len(vetores_) != len(lote):
            raise vetores.VetorInvalido(f"pedi {len(lote)} vetores e voltaram {len(vetores_)}")
        mudancas = []
        for pedaco, vetor in zip(lote, vetores_, strict=True):
            trecho_id = str(uuid.uuid4())
            ids.append(trecho_id)
            mudancas.append(
                (
                    _ref_do_trecho(trecho_id),
                    {
                        "documento": documento_id,
                        "arquivo": nome,
                        "tema_lido": tema_lido,
                        "ordem": pedaco.ordem,
                        "linha_de": pedaco.linha_de,
                        "linha_ate": pedaco.linha_ate,
                        "secao": pedaco.secao,
                        "texto": pedaco.texto,
                        "ativo": False,
                        "apagar_em": momento + APRENDER_VALE,
                        "vetor": _vetor(vetor),
                        "vetor_modelo": vetores.MODELO,
                        "vetor_dim": vetores.DIMENSAO,
                    },
                    True,
                )
            )
        _gravar_em_lotes(mudancas)
    # A 2ª fase: os trechos entram, e o documento por último (a consulta confere o documento).
    _gravar_em_lotes([(_ref_do_trecho(t), {"ativo": True, "apagar_em": None}, False) for t in ids])

    def entrar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        dados = snap.to_dict() if snap.exists else None
        if not dados or dados.get("estado") != APRENDENDO:
            return None, False
        return {
            "estado": APRENDIDO,
            "ativo": True,
            "aprendido_em": momento,
            "apagar_em": None,
        }, True

    if not firestore_comum.trocar(_ref(documento_id), entrar):
        raise RuntimeError(f"o documento {documento_id} sumiu antes de entrar na busca")
    novo = obter(documento_id)
    assert novo is not None
    antigos = [
        d
        for d in ativos()
        if d.id != documento_id and d.nome_lido == novo.nome_lido and d.tema_lido == tema_lido
    ]
    for antigo in antigos:
        _marcar_substituido(antigo.id, documento_id, momento)
    return novo, (antigos[0] if antigos else None)


def _marcar_substituido(antigo: str, novo: str, momento: datetime) -> None:
    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
        dados = snap.to_dict() if snap.exists else None
        if not dados or not dados.get("ativo"):
            return None, None
        return {"ativo": False, "invalida_em": momento, "substituido_por": novo}, None

    firestore_comum.trocar(_ref(antigo), decidir)
    _marcar_trechos(antigo, {"ativo": False})


def esquecer(documento_id: str, agora: datetime | None = None) -> Documento | None:
    """Tira o documento da busca na hora; o texto some em 30 dias. `None` se não existe."""
    momento = _agora(agora)

    def decidir(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, bool]:
        if not snap.exists:
            return None, False
        if (snap.to_dict() or {}).get("esquecido_em") is not None:
            return None, True  # já esquecido: o prazo não recomeça
        mudanca = {"ativo": False, "esquecido_em": momento, "apagar_em": momento + APAGAR_DEPOIS}
        return mudanca, True

    if not firestore_comum.trocar(_ref(documento_id), decidir):
        return None
    esquecido = obter(documento_id)
    assert esquecido is not None
    # Os trechos levam o mesmo prazo (de novo, se um esquecer anterior caiu antes desta parte).
    _marcar_trechos(documento_id, {"ativo": False, "apagar_em": esquecido.apagar_em})
    return esquecido


def devolver(documento_id: str, agora: datetime | None = None) -> Documento | None:
    """Devolve um documento esquecido (antes de sumir) ou substituído; o que estiver ativo com o
    mesmo arquivo no mesmo tema é esquecido (a busca nunca mistura duas versões). `None` se não
    há o que desfazer (um aprender que não terminou não se devolve: o dono manda de novo)."""
    momento = _agora(agora)
    atual = obter(documento_id)
    if atual is None or atual.estado != APRENDIDO:
        return None
    if atual.esquecido_em is not None:
        if atual.apagar_em is not None and atual.apagar_em <= momento:
            return None  # o prazo passou: a TTL vai apagar, e o documento não volta

        def voltar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("esquecido_em") is None:
                return None, None
            vivo = dados.get("invalida_em") is None
            return {"ativo": vivo, "esquecido_em": None, "apagar_em": None}, None

        firestore_comum.trocar(_ref(documento_id), voltar)
    elif atual.invalida_em is not None:

        def reativar(snap: DocumentSnapshot) -> tuple[dict[str, Any] | None, None]:
            dados = snap.to_dict() or {}
            if dados.get("invalida_em") is None:
                return None, None
            return {"ativo": True, "invalida_em": None, "substituido_por": None}, None

        firestore_comum.trocar(_ref(documento_id), reativar)
    else:
        return None
    devolvido = obter(documento_id)
    assert devolvido is not None
    _marcar_trechos(documento_id, {"ativo": devolvido.ativo, "apagar_em": None})
    if devolvido.ativo:
        for outro in ativos():
            if (
                outro.id != devolvido.id
                and outro.nome_lido == devolvido.nome_lido
                and outro.tema_lido == devolvido.tema_lido
            ):
                esquecer(outro.id, momento)
    return obter(documento_id)


def todos() -> list[Documento]:
    """Todos os documentos ainda no banco, do mais novo ao mais velho."""
    return sorted(
        (_documento(s) for s in _colecao().stream()), key=lambda d: d.criado_em, reverse=True
    )


def ativos() -> list[Documento]:
    from google.cloud.firestore import FieldFilter

    consulta = _colecao().where(filter=FieldFilter("ativo", "==", True))
    return sorted(
        (_documento(s) for s in consulta.stream()), key=lambda d: (d.tema_lido, d.nome_lido)
    )


def temas() -> dict[str, tuple[str, list[str]]]:
    """Os temas com documento ativo: {tema lido: (o tema como o dono escreveu, os arquivos)}."""
    saida: dict[str, tuple[str, list[str]]] = {}
    for documento in ativos():
        _tema, arquivos = saida.setdefault(documento.tema_lido, (documento.tema, []))
        arquivos.append(documento.nome)
    return saida


def consultar(tema: str, vetor: list[float], k: int = POR_CONSULTA) -> list[Trecho]:
    """Os `k` trechos ativos do tema mais perto do vetor, do mais perto ao mais longe, só de
    documentos ativos."""
    from google.cloud.firestore import FieldFilter
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

    tema_lido = regras.nome_lido(tema)
    if not tema_lido:
        return []
    consulta = (
        _trechos()
        .where(filter=FieldFilter("tema_lido", "==", tema_lido))
        .where(filter=FieldFilter("ativo", "==", True))
        .find_nearest(
            vector_field="vetor",
            query_vector=_vetor(vetor),
            distance_measure=DistanceMeasure.COSINE,
            limit=k,
            distance_result_field="_distancia",
        )
    )
    achados = [_trecho(s, float(s.get("_distancia"))) for s in consulta.get()]
    vivos: dict[str, bool] = {}
    for trecho in achados:
        if trecho.documento not in vivos:
            documento = obter(trecho.documento) if id_valido(trecho.documento) else None
            vivos[trecho.documento] = bool(documento and documento.ativo)
    validos = [t for t in achados if vivos[t.documento]]
    return sorted(validos, key=lambda t: t.distancia if t.distancia is not None else 2.0)


def da_semana(inicio: datetime, fim: datetime) -> list[Documento]:
    """Os aprendidos ou esquecidos entre `inicio` e `fim` (o resumo de segunda)."""
    inicio, fim = firestore_comum.instante(inicio), firestore_comum.instante(fim)

    def dentro(momento: datetime | None) -> bool:
        return momento is not None and inicio <= momento < fim

    escolhidos = [
        d
        for d in todos()
        if d.estado == APRENDIDO and (dentro(d.aprendido_em) or dentro(d.esquecido_em))
    ]
    return sorted(escolhidos, key=lambda d: d.aprendido_em or d.criado_em)


def por_prefixo(prefixo: str, minimo: int = PREFIXO_MINIMO) -> str | None:
    """O id completo de um prefixo; `None` se nenhum ou mais de um casa."""
    prefixo = (prefixo or "").strip().lower()
    if len(prefixo) < minimo or any(c not in "0123456789abcdef-" for c in prefixo):
        return None
    casam = [s.id for s in _colecao().select([]).stream() if s.id.startswith(prefixo)]
    return casam[0] if len(casam) == 1 else None


def trechos_de(documento_id: str) -> list[Trecho]:
    from google.cloud.firestore import FieldFilter

    consulta = _trechos().where(filter=FieldFilter("documento", "==", documento_id))
    return sorted((_trecho(s) for s in consulta.stream()), key=lambda t: t.ordem)


def sem_vetor() -> list[Trecho]:
    """Os trechos cujo vetor falta ou é de outro modelo ou dimensão (o `--reindexar`)."""
    return [
        t
        for t in (_trecho(s) for s in _trechos().stream())
        if t.vetor_modelo != vetores.MODELO or t.vetor_dim != vetores.DIMENSAO
    ]


def trocar_vetor(trecho_id: str, vetor: list[float]) -> None:
    _ref_do_trecho(trecho_id).update(
        {"vetor": _vetor(vetor), "vetor_modelo": vetores.MODELO, "vetor_dim": vetores.DIMENSAO}
    )


# --- o backup (D68: os documentos e os trechos com o texto, sem o vetor) ------------------------


def _iso(momento: datetime | None) -> str | None:
    return registro_interface.texto_do_instante(momento)


def copia(documento: Documento) -> dict[str, Any]:
    return {
        "id": documento.id,
        "nome": documento.nome,
        "tema": documento.tema,
        "bytes": documento.bytes,
        "n_trechos": documento.n_trechos,
        "impressao": documento.impressao,
        "origem": documento.origem,
        "estado": documento.estado,
        "ativo": documento.ativo,
        "criado_em": _iso(documento.criado_em),
        "aprendido_em": _iso(documento.aprendido_em),
        "invalida_em": _iso(documento.invalida_em),
        "substituido_por": documento.substituido_por,
        "esquecido_em": _iso(documento.esquecido_em),
        "apagar_em": _iso(documento.apagar_em),
    }


def copia_do_trecho(trecho: Trecho) -> dict[str, Any]:
    return {
        "id": trecho.id,
        "documento": trecho.documento,
        "arquivo": trecho.arquivo,
        "tema_lido": trecho.tema_lido,
        "ordem": trecho.ordem,
        "linha_de": trecho.linha_de,
        "linha_ate": trecho.linha_ate,
        "secao": trecho.secao,
        "texto": trecho.texto,
        "ativo": trecho.ativo,
        "apagar_em": _iso(trecho.apagar_em),
    }


def exportar() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documentos = sorted((copia(d) for d in todos()), key=lambda c: c["id"])
    trechos = sorted(
        (copia_do_trecho(_trecho(s)) for s in _trechos().stream()), key=lambda c: c["id"]
    )
    return documentos, trechos


def _instante(texto: str | None) -> datetime | None:
    return firestore_comum.instante(datetime.fromisoformat(texto)) if texto else None


def importar(dados: dict[str, Any]) -> str:
    """A restauração de um documento do backup: o mesmo id e as mesmas marcas, por `create()`.
    Nunca sobrescreve: igual → `igual`; diferente → `diferente`, e o da nuvem fica."""
    from google.api_core.exceptions import AlreadyExists

    nome, tema = cortes.nome_valido(dados["nome"]), cortes.tema_valido(dados["tema"])
    if dados["estado"] not in ESTADOS or dados["origem"] not in ORIGENS:
        raise Recusado("estado ou origem fora do formato")
    documento = dict.fromkeys(_CAMPOS)
    documento.update({c: dados[c] for c in CAMPOS_DA_COPIA if c != "id"})
    documento.update(nome_lido=regras.nome_lido(nome), tema_lido=regras.nome_lido(tema))
    for campo in _INSTANTES:
        documento[campo] = _instante(dados[campo])
    ref = _ref(dados["id"])
    try:
        ref.create(documento)
    except AlreadyExists:
        atual = obter(dados["id"])
        return IGUAL if atual is not None and copia(atual) == dados else DIFERENTE
    return CRIADO


def importar_trecho(dados: dict[str, Any]) -> str:
    """O trecho do backup, sem vetor (o `viking memoria --reindexar` refaz). Nunca sobrescreve."""
    from google.api_core.exceptions import AlreadyExists

    texto = dados["texto"]
    if not isinstance(texto, str) or not texto.strip() or len(texto) > MAX_TEXTO_DO_TRECHO:
        raise Recusado("trecho fora do formato")
    if "\x00" in texto or not id_valido(dados["documento"]):
        raise Recusado("trecho fora do formato")
    campos = dict.fromkeys(_CAMPOS_DO_TRECHO)
    campos.update({c: dados[c] for c in CAMPOS_DA_COPIA_DO_TRECHO if c != "id"})
    campos["apagar_em"] = _instante(dados["apagar_em"])
    ref = _ref_do_trecho(dados["id"])
    try:
        ref.create(campos)
    except AlreadyExists:
        snap = ref.get()
        return IGUAL if copia_do_trecho(_trecho(snap)) == dados else DIFERENTE
    return CRIADO
