"""Um Drive falso para os testes do backup (Sessão 11c, D63): a mesma forma de chamada do
`googleapiclient` (`files().list/create/get_media(...).execute()`), guardando os arquivos em
memória. As consultas (`q`) são as duas que `backup/drive.py` faz, lidas por pedaços: um texto de
consulta novo no código cai aqui como erro, não como resposta inventada.

`falhar_no_create`: o status HTTP que o próximo `create` de arquivo (não de pasta) levanta.
"""

from __future__ import annotations

import httplib2
from googleapiclient.errors import HttpError

PASTA = "application/vnd.google-apps.folder"


class _Pedido:
    def __init__(self, fazer):
        self._fazer = fazer

    def execute(self):
        return self._fazer()


class DriveFalso:
    def __init__(self):
        self.arquivos: list[dict] = []
        self.chamadas: list[str] = []
        self.falhar_no_create: int | None = None

    def files(self):
        return self

    def _novo(self, corpo, conteudo):
        numero = len(self.arquivos) + 1
        arquivo = {
            "id": f"f{numero}",
            "name": corpo["name"],
            "mimeType": corpo.get("mimeType"),
            "parents": list(corpo.get("parents", [])),
            "createdTime": f"2026-10-07T09:00:{numero:02d}.000Z",
            "conteudo": conteudo,
        }
        self.arquivos.append(arquivo)
        return arquivo

    def create(self, body, fields, media_body=None):
        self.chamadas.append("create")

        def fazer():
            if media_body is not None and self.falhar_no_create is not None:
                status, self.falhar_no_create = self.falhar_no_create, None
                raise HttpError(httplib2.Response({"status": str(status)}), b"erro falso")
            conteudo = media_body.getbytes(0, media_body.size()) if media_body else None
            arquivo = self._novo(body, conteudo)
            return {k: arquivo[k] for k in ("id", "name", "createdTime")}

        return _Pedido(fazer)

    def list(self, q, spaces, fields, pageSize, orderBy=None):
        self.chamadas.append("list")
        assert spaces == "drive" and "trashed = false" in q

        def fazer():
            if f"mimeType = '{PASTA}'" in q:
                nome = q.split("name = '", 1)[1].split("'", 1)[0]
                achados = [a for a in self.arquivos if a["mimeType"] == PASTA and a["name"] == nome]
            elif "' in parents" in q:
                pasta = q.split("'", 2)[1]
                achados = [
                    a
                    for a in self.arquivos
                    if pasta in a["parents"] and a["mimeType"] == "application/json"
                ]
                if orderBy == "createdTime desc":
                    achados = sorted(achados, key=lambda a: a["createdTime"], reverse=True)
            else:
                raise AssertionError(f"consulta que o dublê não conhece: {q}")
            campos = ("id", "name", "createdTime")
            return {"files": [{k: a[k] for k in campos} for a in achados[:pageSize]]}

        return _Pedido(fazer)

    def get_media(self, fileId):
        self.chamadas.append("get_media")
        return _Pedido(lambda: next(a["conteudo"] for a in self.arquivos if a["id"] == fileId))

    def de_backup(self) -> list[dict]:
        return [a for a in self.arquivos if a["mimeType"] == "application/json"]
