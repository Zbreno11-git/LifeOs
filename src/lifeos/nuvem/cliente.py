"""O terminal do Mac falando com o motor da nuvem (Sessão 10, D58).

Sem chave em disco: o Mac usa o login do Google Cloud do dono (`gcloud auth application-default
login`, uma vez) só para pedir ao Google um token de identidade **do `viking-cli@`**, com a
audience = a URL do motor e o e-mail dentro. O dono tem permissão de se passar só por essa conta
(`scripts/nuvem.py`, passo "contas"), e o motor só aceita essa conta (`motor.quem_pode`). O token
de usuário do gcloud não serviria: não tem audience (a documentação o chama de "susceptible to
replay").

A cota da chamada de impersonação vai para o projeto do Viking (`with_quota_project`): o login
guarda como projeto de cota o padrão do gcloud, que pode ser outro projeto do dono.

Os instantes chegam em UTC e o fuso do dono entra aqui, na borda. Nada de token em mensagem de
erro: o texto diz o que falhou e o que fazer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lifeos import config
from lifeos.reminders.models import Reminder

PRAZO_S = 30.0
# O `--timeout` do motor (300 s, `scripts/nuvem.py`) mais 20 s: a resposta dele chega antes.
PRAZO_CHAT_S = 320.0
ESCOPO = "https://www.googleapis.com/auth/cloud-platform"


class ErroDaNuvem(RuntimeError):
    """A nuvem não respondeu o que devia; a mensagem é para o dono ler."""


CLI, MAOS = "viking-cli", "viking-maos"


def conta_do_terminal(nome: str = CLI) -> str:
    return f"{nome}@{config.NUVEM_PROJETO}.iam.gserviceaccount.com"


def _sessao(conta: str = CLI) -> Any:
    """Uma sessão HTTP que põe em cada pedido o token de identidade de `conta`: o `viking-cli@`
    (o terminal do dono) ou o `viking-maos@` (as mãos; Sessão 11, D61). O motor confere qual
    conta fala com qual rota."""
    if not config.NUVEM_URL or not config.NUVEM_PROJETO:
        raise ErroDaNuvem("falta VIKING_NUVEM_URL ou VIKING_NUVEM_PROJETO no .env")
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.exceptions import DefaultCredentialsError
    from google.auth.transport.requests import AuthorizedSession

    try:
        dono, _projeto = google.auth.default(scopes=[ESCOPO])
    except DefaultCredentialsError:
        raise ErroDaNuvem(
            "este computador não tem o login do Google Cloud: rode "
            "`gcloud auth application-default login` uma vez"
        ) from None
    if hasattr(dono, "with_quota_project"):
        dono = dono.with_quota_project(config.NUVEM_PROJETO)
    terminal = impersonated_credentials.Credentials(
        source_credentials=dono,
        target_principal=conta_do_terminal(conta),
        target_scopes=[ESCOPO],
        lifetime=300,
    )
    token = impersonated_credentials.IDTokenCredentials(
        terminal, target_audience=config.NUVEM_URL, include_email=True
    )
    return AuthorizedSession(token)


def _chamar(
    sessao: Any, metodo: str, rota: str, *, corpo: Any = None, prazo: float = PRAZO_S
) -> dict[str, Any]:
    """Um pedido ao motor, com o erro dito em português (nunca o token, nunca a conversa)."""
    import requests
    from google.auth.exceptions import RefreshError, TransportError

    try:
        resposta = sessao.request(metodo, f"{config.NUVEM_URL}{rota}", json=corpo, timeout=prazo)
    except RefreshError:
        raise ErroDaNuvem(
            "o Google não deu o token da conta do Viking (o login do Google Cloud venceu, ou falta "
            "a permissão de se passar por ela: `python scripts/nuvem.py` no VPS mostra)"
        ) from None
    except requests.Timeout:
        raise ErroDaNuvem(
            f"a nuvem não respondeu em {prazo:.0f} s (o motor pode ter agido: pergunte a ele o que "
            "fez antes de repetir)"
        ) from None
    except (requests.ConnectionError, TransportError):
        raise ErroDaNuvem("a nuvem não respondeu (rede, ou o motor fora do ar)") from None
    if resposta.status_code in (401, 403):
        raise ErroDaNuvem(f"a nuvem recusou a identidade (HTTP {resposta.status_code})")
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    if resposta.status_code != 200:
        detalhe = dados.get("erro") if isinstance(dados, dict) else None
        texto = f": {detalhe}" if isinstance(detalhe, str) and detalhe else ""
        raise ErroDaNuvem(f"a nuvem respondeu HTTP {resposta.status_code}{texto}")
    if dados is None:
        raise ErroDaNuvem("a nuvem respondeu algo que não é JSON")
    if not isinstance(dados, dict):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado")
    return dados


def sessao_de_chat() -> Any:
    """Uma sessão HTTP para a conversa inteira (o token renova sozinho quando vence)."""
    return _sessao()


def capacidades(sessao: Any) -> dict[str, Any]:
    """O que o motor no ar tem (`/versao`): o terminal diz isso na abertura, sem prometer o que
    não está lá (o Gmail só com o token dele na nuvem; Sessão 11, D61)."""
    return _chamar(sessao, "GET", "/versao")


def turno_de_chat(sessao: Any, pedido: dict[str, Any]) -> dict[str, Any]:
    """Um turno do chat da nuvem (`POST /chat`). O prazo é o do motor mais uma folga."""
    return _chamar(sessao, "POST", "/chat", corpo=pedido, prazo=PRAZO_CHAT_S)


def sessao_das_maos() -> Any:
    """A sessão do `viking maos`: o token do `viking-maos@`, que só fala com `/maos/*`."""
    return _sessao(MAOS)


def pegar_tarefa(sessao: Any, por: str) -> dict[str, Any] | None:
    """A próxima tarefa de navegador da nuvem, crua (o Mac a valida), ou `None`."""
    dados = _chamar(sessao, "POST", "/maos/pegar", corpo={"por": por})
    tarefa = dados.get("tarefa")
    if tarefa is not None and not isinstance(tarefa, dict):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado")
    return tarefa


def entregar_tarefa(sessao: Any, tarefa_id: str, por: str, resultado: str) -> bool:
    """Devolve o texto (já redigido) da tarefa; `False` se a nuvem não a aceitou (não era mais
    nossa, ou o turno desistiu)."""
    dados = _chamar(
        sessao,
        "POST",
        "/maos/entregar",
        corpo={"id": tarefa_id, "por": por, "resultado": resultado},
    )
    return dados.get("aceita") is True


def _instante(texto: Any) -> datetime | None:
    if texto is None:
        return None
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:  # a nuvem só manda instantes; sem fuso seria adivinhar
        raise ErroDaNuvem("a nuvem mandou um horário sem fuso")
    return momento


def _lembrete(item: Any) -> Reminder:
    try:
        return Reminder(
            id=item["id"],
            type=item["type"],
            title=item["title"],
            body=item["body"],
            tags=list(item["tags"]),
            due_at=_instante(item["due_at"]),
            completed_at=_instante(item.get("completed_at")),
            created_at=_instante(item["created_at"]),
            enviado_em=_instante(item["enviado_em"]),
            envio_estado=item["envio_estado"],
        )
    except (KeyError, TypeError, ValueError):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado") from None


def lembretes_pendentes(sessao: Any = None) -> list[Reminder]:
    """Os pendentes que moram no Firestore, pela ordem que o motor manda."""
    dados = _chamar(sessao or _sessao(), "GET", "/lembretes")
    itens = dados.get("lembretes")
    if not isinstance(itens, list):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado")
    return [_lembrete(item) for item in itens]


# --- os lembretes do Mac depois da migração (Sessão 11, D61) ------------------------------------


def criar_lembrete(titulo: str, corpo: str, tags: str, quando: str, source: str) -> Reminder:
    """Cria na nuvem; `quando` é um instante ISO 8601 com fuso, ou vazio (o fuso do dono foi
    decidido no Mac, na borda)."""
    corpo_do_pedido = {
        "titulo": titulo,
        "corpo": corpo,
        "tags": tags,
        "quando": quando,
        "source": source,
    }
    dados = _chamar(_sessao(), "POST", "/lembretes/criar", corpo=corpo_do_pedido)
    return _lembrete(dados.get("lembrete"))


def concluir_lembrete(reminder_id: str) -> Reminder | None:
    dados = _chamar(_sessao(), "POST", "/lembretes/concluir", corpo={"id": reminder_id})
    item = dados.get("lembrete")
    return None if item is None else _lembrete(item)


def importar_lembretes(sessao: Any, lote: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Copia um lote (até `transporte.MAX_LOTE`) para a nuvem: {criados, iguais, diferentes}."""
    dados = _chamar(sessao, "POST", "/lembretes/importar", corpo={"lembretes": lote})
    resposta = {c: dados.get(c) for c in ("criados", "iguais", "diferentes")}
    if not all(isinstance(v, list) for v in resposta.values()):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado")
    return {c: [str(i) for i in v or []] for c, v in resposta.items()}


def impressoes_dos_lembretes(sessao: Any) -> dict[str, str]:
    """{id: impressão} de todos os lembretes da nuvem (`reminders/transporte.impressao`)."""
    dados = _chamar(sessao, "GET", "/lembretes/impressoes")
    impressoes = dados.get("impressoes")
    if not isinstance(impressoes, dict):
        raise ErroDaNuvem("a nuvem respondeu num formato inesperado")
    return {str(k): str(v) for k, v in impressoes.items()}
