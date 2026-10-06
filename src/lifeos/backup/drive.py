"""O Drive do dono para o backup (Sessão 11c, D63): uma pasta, arquivos que só se acumulam.

O escopo é `drive.file`: o Viking só enxerga os arquivos que ele mesmo criou (não é escopo
sensível, segundo o Google). Este módulo só **cria** (a pasta e o arquivo), **lista** e **baixa**:
nada apaga, atualiza, move para a lixeira nem compartilha (resposta do dono, 2026-10-06: todas as
cópias ficam). `tests/test_backup_drive.py` lê o código e reprova qualquer outra chamada.

O token mora em `secrets/google_token_drive.json` no Mac (`viking backup --login`) e, na nuvem, no
volume do segredo `viking-drive`, subido do Mac (o VPS não o guarda). `google_auth.servico` escolhe.

Subir passa por `registro.acao("backup.drive")`, como todo efeito externo: uma falha do Google
depois de o pedido sair (5xx, tempo esgotado) é `incerta`.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lifeos import config, registro

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PASTA = "Viking — backups"
_TIPO_DA_PASTA = "application/vnd.google-apps.folder"
_TIPO = "application/json"


class FalhaDoDrive(RuntimeError):
    """O Drive recusou ou não respondeu. `incerta`: o arquivo pode ter sido criado."""

    def __init__(self, mensagem: str, *, incerta: bool = False) -> None:
        super().__init__(mensagem)
        self.incerta = incerta


@dataclass(frozen=True)
class Arquivo:
    id: str
    nome: str
    criado_em: str


def _servico() -> Any:
    from lifeos import google_auth

    return google_auth.servico("drive", "v3", SCOPES, config.DRIVE_TOKEN_PATH)


def login() -> None:
    """Faz (ou confere) o login do Drive: no Mac, abre a tela do Google se preciso."""
    _servico()


def _descrever(exc: BaseException) -> str:
    """O erro sem o corpo cru do Google (que traz o número do projeto OAuth)."""
    from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

    if isinstance(exc, HttpError):
        try:
            erros = json.loads(exc.content.decode("utf-8"))["error"].get("errors") or []
            motivos = sorted({str(e.get("reason")) for e in erros if isinstance(e, dict)})
        except (ValueError, KeyError, TypeError, AttributeError):
            motivos = []
        status = getattr(exc.resp, "status", "?")
        return f"HTTP {status}" + (f" ({', '.join(motivos)})" if motivos else "")
    return type(exc).__name__


def _executar(pedido: Any, *, escreve: bool) -> Any:
    from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

    try:
        return pedido.execute()
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        certa = isinstance(status, int) and 400 <= status < 500
        raise FalhaDoDrive(_descrever(exc), incerta=escreve and not certa) from None
    except Exception as exc:  # noqa: BLE001 - tempo esgotado, conexão: se escrevia, pode ter criado
        raise FalhaDoDrive(_descrever(exc), incerta=escreve) from None


def _achar_pasta(servico: Any) -> str | None:
    consulta = f"mimeType = '{_TIPO_DA_PASTA}' and name = '{PASTA}' and trashed = false"
    resposta = _executar(
        servico.files().list(
            q=consulta, spaces="drive", fields="files(id, createdTime)", pageSize=10
        ),
        escreve=False,
    )
    pastas = sorted(resposta.get("files", []), key=lambda f: f.get("createdTime", ""))
    return pastas[0]["id"] if pastas else None  # a mais velha, se um dia houver duas


def subir(nome: str, conteudo: bytes, contagens: dict[str, int]) -> Arquivo:
    """Cria o arquivo na pasta (e a pasta, na primeira vez). Nunca substitui um que exista."""
    from googleapiclient.http import MediaInMemoryUpload  # type: ignore[import-untyped]

    with registro.acao("backup.drive", {"arquivo": nome, **contagens}) as marca:
        servico = _servico()
        pasta = _achar_pasta(servico)
        if pasta is None:
            criada = _executar(
                servico.files().create(
                    body={"name": PASTA, "mimeType": _TIPO_DA_PASTA}, fields="id"
                ),
                escreve=True,
            )
            pasta = criada["id"]
        midia = MediaInMemoryUpload(conteudo, mimetype=_TIPO, resumable=False)
        criado = _executar(
            servico.files().create(
                body={"name": nome, "parents": [pasta], "mimeType": _TIPO},
                media_body=midia,
                fields="id, name, createdTime",
            ),
            escreve=True,
        )
        arquivo = Arquivo(criado["id"], criado["name"], criado.get("createdTime", ""))
        marca.feito({"arquivo_id": arquivo.id, "bytes": len(conteudo)})
    return arquivo


def ultimo() -> Arquivo | None:
    """O arquivo mais novo da pasta, ou `None` se ainda não há backup."""
    servico = _servico()
    pasta = _achar_pasta(servico)
    if pasta is None:
        return None
    resposta = _executar(
        servico.files().list(
            q=f"'{pasta}' in parents and trashed = false and mimeType = '{_TIPO}'",
            spaces="drive",
            orderBy="createdTime desc",
            fields="files(id, name, createdTime)",
            pageSize=1,
        ),
        escreve=False,
    )
    arquivos = resposta.get("files", [])
    if not arquivos:
        return None
    f = arquivos[0]
    return Arquivo(f["id"], f["name"], f.get("createdTime", ""))


def baixar(arquivo_id: str) -> bytes:
    conteudo = _executar(_servico().files().get_media(fileId=arquivo_id), escreve=False)
    if not isinstance(conteudo, bytes):
        raise FalhaDoDrive("o Drive devolveu algo que não é o arquivo")
    return conteudo
