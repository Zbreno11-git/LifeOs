"""O motor do Viking no Cloud Run (Sessão 10, D58).

Fechado por duas paredes, e a segunda não confia na primeira:
1. **o IAM do Cloud Run** (`--no-allow-unauthenticated`, `run.invoker` só para o `viking-cli@`):
   um pedido sem token válido nem chega aqui, e não é cobrado;
2. **este código**, na primeira instrução de toda rota (`_quem`): verifica a assinatura do token
   de identidade (emitido pelo Google, com a audience = a URL deste serviço) e confere o e-mail
   na lista **daquela rota** (`QUEM_FALA`, `quem_pode`; Sessão 11, D61): o terminal do dono, as
   mãos do Mac e o agendador têm cada um a sua porta, e rota fora do mapa não tem ninguém. Se
   alguém afrouxasse o IAM, um token forjado ou de outra conta continuaria recusado.
   `tests/test_motor.py` lê o código e reprova rota sem `_quem` na frente ou fora do mapa.

O cliente manda o token em `Authorization: Bearer` (o `X-Serverless-Authorization` chega ao
contêiner **sem** a assinatura, segundo a documentação do Cloud Run lida em 2026-09-29, e aí não
daria para verificar). Nada de conteúdo na URL: o log de pedidos do Cloud Run guarda a URL e não o
corpo (lido em 2026-09-29); e este módulo não loga título nem corpo de nada.

Desde a Sessão 10b (D59) o motor roda o chat (`POST /chat`, `assistant/na_nuvem.py`). As rotas
são `async`, mas todo trabalho que bloqueia (a verificação do token, o Firestore, o turno com o
Gemini) roda numa thread (`run_in_threadpool`): um turno de chat não para os outros pedidos da
instância. O corpo do `/chat` tem teto (`MAX_CORPO`) e nunca vai ao log.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from lifeos import config, registro
from lifeos.reminders import service
from lifeos.reminders.models import Reminder

log = logging.getLogger("viking.motor")
COMMIT = os.getenv("VIKING_COMMIT", "")
EMISSORES = ("https://accounts.google.com", "accounts.google.com")
MAX_CORPO = 4 * 1024 * 1024  # o histórico medido chegou a 7 KB em 5 turnos (2026-09-30)
MAX_CORPO_DAS_MAOS = 64 * 1024  # o resultado de uma tarefa tem até 20 mil caracteres


CLI, MAOS, AGENDADOR = "viking-cli", "viking-maos", "viking-agendador"


def quem_pode(rota: str) -> frozenset[str]:
    """Os e-mails que falam com esta rota (`QUEM_FALA`, no fim do módulo, junto das rotas)."""
    if not config.NUVEM_PROJETO:
        return frozenset()
    contas = QUEM_FALA.get(rota, frozenset())
    return frozenset(f"{c}@{config.NUVEM_PROJETO}.iam.gserviceaccount.com" for c in contas)


_SESSAO: Any = None


def _verificar(token: str) -> dict[str, Any]:
    """Os dados do token, depois de conferir assinatura (os certificados do Google), emissor,
    validade e audience. Levanta `ValueError` se qualquer um falhar."""
    global _SESSAO
    import google.auth.transport.requests
    import requests
    from google.oauth2 import id_token

    if not config.NUVEM_URL:
        raise ValueError("VIKING_NUVEM_URL vazio: sem audience, nenhum token vale")
    if _SESSAO is None:
        _SESSAO = requests.Session()  # reaproveita a conexão com os certificados do Google
    requisicao = google.auth.transport.requests.Request(session=_SESSAO)
    dados = dict(id_token.verify_token(token, requisicao, audience=config.NUVEM_URL))
    if dados.get("iss") not in EMISSORES:
        raise ValueError("emissor que não é o Google")
    return dados


async def _quem(request: Request) -> str:
    """A primeira instrução de toda rota: o e-mail de quem pediu, ou 401/403. A verificação busca
    os certificados do Google (rede): roda numa thread."""
    cabecalho = request.headers.get("authorization", "")
    tipo, _, token = cabecalho.partition(" ")
    if tipo.lower() != "bearer" or not token:
        raise HTTPException(401, "sem token")
    try:
        dados = await run_in_threadpool(_verificar, token)
    except ValueError:
        raise HTTPException(401, "token recusado") from None
    email = dados.get("email", "")
    if not dados.get("email_verified") or email not in quem_pode(request.url.path):
        log.warning("identidade recusada")  # sem o e-mail: o log é do projeto, não do dono
        raise HTTPException(403, "identidade sem acesso")
    return email


def _instante(momento: Any) -> str | None:
    return momento.isoformat() if momento is not None else None


def _lembrete(lembrete: Reminder) -> dict[str, Any]:
    """Instantes em UTC, ISO 8601 com fuso: o fuso do dono é do cliente (a borda)."""
    return {
        "id": lembrete.id,
        "type": lembrete.type,
        "title": lembrete.title,
        "body": lembrete.body,
        "tags": lembrete.tags,
        "due_at": _instante(lembrete.due_at),
        "completed_at": _instante(lembrete.completed_at),
        "created_at": _instante(lembrete.created_at),
        "enviado_em": _instante(lembrete.enviado_em),
        "envio_estado": lembrete.envio_estado,
    }


async def versao(request: Request) -> JSONResponse:
    """O commit no ar e o que este motor tem (o terminal do Mac diz isso na abertura)."""
    await _quem(request)
    from lifeos.backup import rodada
    from lifeos.reminders import agendador

    ligado = await run_in_threadpool(agendador.ligado)
    backup_em = await run_in_threadpool(rodada.ultimo) if config.drive_no_motor() else None
    return JSONResponse(
        {
            "commit": COMMIT,
            "gmail": config.gmail_no_motor(),
            "maos": True,
            "envio_de_lembretes": ligado,
            "backup": config.drive_no_motor(),
            "backup_em": _instante(backup_em),
        }
    )


async def lembretes(request: Request) -> JSONResponse:
    await _quem(request)
    pendentes = await run_in_threadpool(service.pendentes)
    return JSONResponse({"lembretes": [_lembrete(r) for r in pendentes]})


def _vencidos_24h() -> int:
    agora = datetime.now(UTC)
    return len(service.store.vencidos(agora - timedelta(hours=24), agora))


async def fumaca_vencidos(request: Request) -> JSONResponse:
    """Só leitura: exerce a consulta dos vencidos na produção, que pede o índice composto (o
    emulador não pede). Devolve só a contagem."""
    await _quem(request)
    return JSONResponse({"vencidos_24h": await run_in_threadpool(_vencidos_24h)})


def _consultas_do_registro() -> dict[str, int]:
    """Cada consulta do registro com parâmetros que não acham nada: prova, na produção, que os
    índices que ela pede existem. Só leitura."""
    agora = datetime.now(UTC)
    return {
        "do_turno": len(registro.do_turno("fumaca:0")),
        "recentes": len(registro.recentes(dias=1, limite=1)),
        "contaveis": len(registro.contaveis("fumaca", desde=agora - timedelta(hours=1))),
        "ultima_desfazivel": int(
            registro.ultima_desfazivel(
                ("fumaca",), prefixo_turno="fumaca:", janela=timedelta(hours=1)
            )
            is not None
        ),
        "obter": int(registro.obter(0) is not None),
    }


async def fumaca_registro(request: Request) -> JSONResponse:
    await _quem(request)
    return JSONResponse(await run_in_threadpool(_consultas_do_registro))


def _segredos() -> dict[str, bool]:
    """A chave do Gemini lê e os tokens da agenda e do Gmail renovam (o Gmail desde a 10c). Nenhuma
    chamada paga nem à API do Gmail; nenhum valor sai."""
    from lifeos import google_auth
    from lifeos.calendar import oauth
    from lifeos.gmail import oauth as gmail_oauth

    resposta = {"gemini": False, "agenda": False, "gmail": False}
    try:
        resposta["gemini"] = bool(config.gemini_chave())
    except RuntimeError:
        log.warning("segredo do gemini: não leu")
    try:
        creds = google_auth.credenciais_da_nuvem(oauth.SCOPES, config.GOOGLE_TOKEN_PATH)
        resposta["agenda"] = bool(creds.valid)
    except (RuntimeError, ValueError) as exc:
        log.warning("segredo da agenda: %s", type(exc).__name__)
    try:
        creds = google_auth.credenciais_da_nuvem(gmail_oauth.SCOPES, config.GMAIL_TOKEN_PATH)
        resposta["gmail"] = bool(creds.valid)
    except (RuntimeError, ValueError) as exc:
        log.warning("segredo do gmail: %s", type(exc).__name__)
    return resposta


async def fumaca_segredos(request: Request) -> JSONResponse:
    await _quem(request)
    return JSONResponse(await run_in_threadpool(_segredos))


def _turno(dados: Any) -> dict[str, Any]:
    from lifeos.assistant import na_nuvem  # o laço do Gemini: pesado, só para quem conversa

    return na_nuvem.turno(dados)


async def chat(request: Request) -> JSONResponse:
    """Um turno do chat da nuvem (`assistant/na_nuvem.py`). O corpo (a conversa inteira) nunca
    vai ao log; um erro diz só o tipo."""
    await _quem(request)
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > MAX_CORPO:
        return JSONResponse({"erro": "a conversa passou do tamanho que o motor aceita"}, 413)
    corpo = await request.body()
    if len(corpo) > MAX_CORPO:
        return JSONResponse({"erro": "a conversa passou do tamanho que o motor aceita"}, 413)
    try:
        dados = json.loads(corpo)
    except ValueError:
        return JSONResponse({"erro": "o corpo do pedido não é JSON"}, 400)
    try:
        resposta = await run_in_threadpool(_turno, dados)
    except ValueError as exc:  # o pedido veio torto: a mensagem não ecoa conteúdo
        return JSONResponse({"erro": str(exc)}, 400)
    except Exception as exc:  # noqa: BLE001 - o log leva só o tipo, nunca a conversa
        log.error("turno do chat falhou: %s", type(exc).__name__)
        return JSONResponse({"erro": f"o motor falhou ({type(exc).__name__})"}, 500)
    return JSONResponse(resposta)


# Quem fala com cada rota (Sessão 11, D61): uma conta, uma porta. O `viking-maos@` vive num Mac e
# o `viking-agendador@` é o Cloud Scheduler: nenhum dos dois lê a conversa nem os lembretes.
QUEM_FALA: dict[str, frozenset[str]] = {
    "/versao": frozenset({CLI}),
    "/lembretes": frozenset({CLI}),
    "/fumaca/vencidos": frozenset({CLI}),
    "/fumaca/registro": frozenset({CLI}),
    "/fumaca/segredos": frozenset({CLI}),
    "/chat": frozenset({CLI}),
    "/maos/pegar": frozenset({MAOS}),
    "/maos/entregar": frozenset({MAOS}),
    "/lembretes/criar": frozenset({CLI}),
    "/lembretes/concluir": frozenset({CLI}),
    "/lembretes/importar": frozenset({CLI}),
    "/lembretes/impressoes": frozenset({CLI}),
    "/tarefas/lembretes": frozenset({AGENDADOR}),
    "/tarefas/backup": frozenset({AGENDADOR}),
    "/backup/importar": frozenset({CLI}),
}


# --- os lembretes do Mac depois da migração e o envio pela nuvem (Sessão 11, D61) -------------

MAX_CORPO_DA_COPIA = 1024 * 1024  # um lote de 100 lembretes com folga


def _texto_do_pedido(dados: dict[str, Any], campo: str) -> str:
    valor = dados.get(campo, "")
    if not isinstance(valor, str):
        raise ValueError(f"{campo} tem de ser texto")  # noqa: TRY004 - o motor: 400
    return valor


def _criar(dados: Any) -> dict[str, Any]:
    if not isinstance(dados, dict):
        raise ValueError("o pedido tem de ser um objeto JSON")  # noqa: TRY004 - o motor: 400
    quando = _texto_do_pedido(dados, "quando")
    if quando and datetime.fromisoformat(quando).tzinfo is None:
        raise ValueError("quando tem de ser um instante com fuso (o Mac decide o fuso)")
    titulo = _texto_do_pedido(dados, "titulo")
    if not titulo.strip():
        raise ValueError("o lembrete precisa de um título")
    registro.ORIGEM.set("mac")
    lembrete = service.criar_lembrete(
        titulo,
        _texto_do_pedido(dados, "corpo"),
        _texto_do_pedido(dados, "tags"),
        quando,
        source=_texto_do_pedido(dados, "source") or "mac",
    )
    return {"lembrete": _lembrete(lembrete)}


def _concluir(dados: Any) -> dict[str, Any]:
    if not isinstance(dados, dict) or not isinstance(dados.get("id"), str):
        raise ValueError("o pedido tem de ter o id do lembrete")  # noqa: TRY004 - o motor: 400
    registro.ORIGEM.set("mac")
    lembrete = service.concluir(dados["id"])
    return {"lembrete": _lembrete(lembrete) if lembrete else None}


def _importar(dados: Any) -> dict[str, Any]:
    from lifeos.reminders import store_firestore, transporte

    lista = dados.get("lembretes") if isinstance(dados, dict) else None
    if not isinstance(lista, list) or not 1 <= len(lista) <= transporte.MAX_LOTE:
        raise ValueError(f"o lote tem de ter de 1 a {transporte.MAX_LOTE} lembretes")
    lembretes = [transporte.de_dict(item) for item in lista]  # tudo conferido antes de gravar
    registro.ORIGEM.set("mac")
    resposta: dict[str, list[str]] = {"criados": [], "iguais": [], "diferentes": []}
    chave = {
        store_firestore.CRIADO: "criados",
        store_firestore.IGUAL: "iguais",
        store_firestore.DIFERENTE: "diferentes",
    }
    with registro.acao("lembrete.importar", {"quantos": len(lembretes)}) as marca:
        for lembrete in lembretes:
            resposta[chave[store_firestore.importar(lembrete)]].append(str(lembrete.id))
        marca.feito({c: len(v) for c, v in resposta.items()})
    return resposta


def _impressoes() -> dict[str, Any]:
    """A impressão de cada lembrete e, desde a 11c (D63), quando nasceu e quando mudou pela última
    vez: o `viking backup --conferir` separa "mudou depois do backup" de uma divergência."""
    from lifeos.reminders import store_firestore, transporte

    lembretes = store_firestore.todos()
    return {
        "impressoes": {str(r.id): transporte.impressao(r) for r in lembretes},
        "instantes": {
            str(r.id): {"criado": _instante(r.created_at), "mudou": _instante(r.updated_at)}
            for r in lembretes
        },
    }


def _importar_do_backup(dados: Any) -> dict[str, Any]:
    """Um lote de ações e meses de gasto de um backup (`viking backup --restaurar`, D63): tudo
    conferido pelo formato antes de gravar; nunca sobrescreve."""
    from lifeos import custos
    from lifeos.backup import formato

    if not isinstance(dados, dict) or set(dados) != {"acoes", "gastos"}:
        raise ValueError("o pedido tem de ter acoes e gastos")
    acoes, gastos = dados["acoes"], dados["gastos"]
    if not isinstance(acoes, list) or not isinstance(gastos, list):
        raise ValueError("acoes e gastos têm de ser listas")  # noqa: TRY004 - o motor: 400
    if not 1 <= len(acoes) + len(gastos) <= formato.LOTE_DO_BACKUP:
        raise ValueError(f"o lote tem de ter de 1 a {formato.LOTE_DO_BACKUP} itens")
    acoes = [formato.acao_conferida(a, f"ação {n}") for n, a in enumerate(acoes, 1)]
    gastos = [formato.gasto_conferido(g, f"gasto {n}") for n, g in enumerate(gastos, 1)]
    registro.ORIGEM.set("mac")
    resposta: dict[str, Any] = {
        "acoes": {"criadas": 0, "iguais": 0, "diferentes": []},
        "gastos": {"criados": 0, "iguais": 0, "diferentes": []},
    }
    with registro.acao("backup.restaurar", {"acoes": len(acoes), "gastos": len(gastos)}) as marca:
        for acao in acoes:
            resultado = registro.importar(acao)
            if resultado == "diferente":
                resposta["acoes"]["diferentes"].append(acao["id"])
            else:
                resposta["acoes"]["criadas" if resultado == "criada" else "iguais"] += 1
        for gasto in gastos:
            resultado = custos.importar_gasto(gasto)
            if resultado == "diferente":
                resposta["gastos"]["diferentes"].append(gasto["mes"])
            else:
                resposta["gastos"]["criados" if resultado == "criado" else "iguais"] += 1
        marca.feito(
            {
                "acoes_criadas": resposta["acoes"]["criadas"],
                "gastos_criados": resposta["gastos"]["criados"],
            }
        )
    return resposta


async def _lembretes_post(request: Request, fazer: Any, teto: int) -> JSONResponse:
    dados = await _corpo_pequeno(request, teto)
    if dados is None:
        return JSONResponse({"erro": "o pedido passou do tamanho ou não é JSON"}, 400)
    try:
        return JSONResponse(await run_in_threadpool(fazer, dados))
    except ValueError as exc:  # o pedido veio torto: a mensagem não ecoa conteúdo
        return JSONResponse({"erro": str(exc)}, 400)


async def lembretes_criar(request: Request) -> JSONResponse:
    """O Mac cria um lembrete (depois da migração): a ação e o registro moram aqui (D57)."""
    await _quem(request)
    return await _lembretes_post(request, _criar, MAX_CORPO_DAS_MAOS)


async def lembretes_concluir(request: Request) -> JSONResponse:
    await _quem(request)
    return await _lembretes_post(request, _concluir, MAX_CORPO_DAS_MAOS)


async def lembretes_importar(request: Request) -> JSONResponse:
    """Um lote da migração do Mac: idempotente pelo id, nunca sobrescreve."""
    await _quem(request)
    return await _lembretes_post(request, _importar, MAX_CORPO_DA_COPIA)


async def backup_importar(request: Request) -> JSONResponse:
    """Um lote da restauração de um backup (Sessão 11c, D63): idempotente, nunca sobrescreve."""
    await _quem(request)
    return await _lembretes_post(request, _importar_do_backup, MAX_CORPO)


async def lembretes_impressoes(request: Request) -> JSONResponse:
    """A conferência da cópia: a impressão de cada lembrete da nuvem (nenhum título sai)."""
    await _quem(request)
    return JSONResponse(await run_in_threadpool(_impressoes))


def _rodada() -> dict[str, Any]:
    from lifeos.reminders import agendador

    registro.ORIGEM.set("agendador")
    return agendador.rodar()


async def tarefas_lembretes(request: Request) -> JSONResponse:
    """A rodada do envio, disparada pelo Cloud Scheduler a cada minuto (só o
    `viking-agendador@`). A resposta tem só contagens; um erro diz só o tipo."""
    await _quem(request)
    try:
        return JSONResponse(await run_in_threadpool(_rodada))
    except Exception as exc:  # noqa: BLE001 - o log leva só o tipo, nunca um título
        log.error("rodada dos lembretes falhou: %s", type(exc).__name__)
        return JSONResponse({"erro": f"a rodada falhou ({type(exc).__name__})"}, 500)


def _backup() -> dict[str, Any]:
    from lifeos.backup import rodada

    registro.ORIGEM.set("agendador")
    return rodada.rodar(commit=COMMIT)


async def tarefas_backup(request: Request) -> JSONResponse:
    """O backup do dia no Drive (Sessão 11c, D63), disparado pelo Cloud Scheduler (só o
    `viking-agendador@`). A resposta tem só contagens e o nome do arquivo; um erro diz só o tipo."""
    await _quem(request)
    try:
        return JSONResponse(await run_in_threadpool(_backup))
    except Exception as exc:  # noqa: BLE001 - o log leva só o tipo, nunca um título
        log.error("o backup falhou: %s", type(exc).__name__)
        return JSONResponse({"erro": f"o backup falhou ({type(exc).__name__})"}, 500)


async def _corpo_pequeno(request: Request, teto: int) -> Any:
    """O JSON de um pedido pequeno, ou `None` se passou do teto ou não é JSON."""
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > teto:
        return None
    corpo = await request.body()
    if len(corpo) > teto:
        return None
    try:
        return json.loads(corpo)
    except ValueError:
        return None


def _pegar(dados: Any) -> dict[str, Any]:
    from lifeos.maos import fila_firestore

    por = dados.get("por") if isinstance(dados, dict) else None
    tarefa = fila_firestore.pegar(por, agora=datetime.now(UTC))
    return {"tarefa": tarefa.como_dict() if tarefa else None}


async def maos_pegar(request: Request) -> JSONResponse:
    """As mãos do Mac perguntam se há tarefa de navegador (Sessão 11, D61). Só o `viking-maos@`."""
    await _quem(request)
    dados = await _corpo_pequeno(request, MAX_CORPO_DAS_MAOS)
    try:
        return JSONResponse(await run_in_threadpool(_pegar, dados))
    except ValueError as exc:  # `TarefaInvalida` e afins: o pedido veio torto
        return JSONResponse({"erro": str(exc)}, 400)


def _entregar(dados: Any) -> dict[str, Any]:
    from lifeos.maos import fila_firestore

    if not isinstance(dados, dict) or not isinstance(dados.get("resultado"), str):
        raise ValueError("a entrega tem de ter id, por e resultado (texto)")  # noqa: TRY004 - 400
    aceita = fila_firestore.entregar(str(dados.get("id")), dados.get("por"), dados["resultado"])
    return {"aceita": aceita}


async def maos_entregar(request: Request) -> JSONResponse:
    """O resultado de uma tarefa, já redigido no Mac. O texto da página nunca vai ao log."""
    await _quem(request)
    dados = await _corpo_pequeno(request, MAX_CORPO_DAS_MAOS)
    if dados is None:
        return JSONResponse({"erro": "a entrega passou do tamanho ou não é JSON"}, 400)
    try:
        return JSONResponse(await run_in_threadpool(_entregar, dados))
    except ValueError as exc:
        return JSONResponse({"erro": str(exc)}, 400)


ROTAS = [
    Route("/versao", versao, methods=["GET"]),
    Route("/lembretes", lembretes, methods=["GET"]),
    Route("/fumaca/vencidos", fumaca_vencidos, methods=["GET"]),
    Route("/fumaca/registro", fumaca_registro, methods=["GET"]),
    Route("/fumaca/segredos", fumaca_segredos, methods=["GET"]),
    Route("/chat", chat, methods=["POST"]),
    Route("/maos/pegar", maos_pegar, methods=["POST"]),
    Route("/maos/entregar", maos_entregar, methods=["POST"]),
    Route("/lembretes/criar", lembretes_criar, methods=["POST"]),
    Route("/lembretes/concluir", lembretes_concluir, methods=["POST"]),
    Route("/lembretes/importar", lembretes_importar, methods=["POST"]),
    Route("/lembretes/impressoes", lembretes_impressoes, methods=["GET"]),
    Route("/tarefas/lembretes", tarefas_lembretes, methods=["POST"]),
    Route("/tarefas/backup", tarefas_backup, methods=["POST"]),
    Route("/backup/importar", backup_importar, methods=["POST"]),
]
app = Starlette(routes=ROTAS)
