"""`viking financas --conectar`: a janela oficial da Pluggy (Pluggy Connect), numa página local.

Existe porque o Dashboard da Pluggy não mostrou ao dono onde conectar o MeuPluggy (2026-09-26).
O fluxo: token curto da Pluggy → página servida só em 127.0.0.1, num caminho aleatório → o
widget, já no conector MeuPluggy, faz o login do Meu Pluggy (OAuth, segundo `GET
/connectors/200`) → no `onSuccess`, a página manda o ID da conexão de volta a este processo →
o CLI confere o ID na API antes de mostrar. Um banco por rodada.

O caminho aleatório (`segredo`) é o que impede outra aba do navegador de mandar um ID falso para
a porta local, e é o único lugar em que o token de conexão aparece.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import html
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from lifeos.financas.pluggy import MEUPLUGGY, EntradaInvalida, id_valido

# Versão fixa (a da documentação da Pluggy em 2026-09-26; conferido que o arquivo existe na CDN).
SCRIPT = "https://cdn.pluggy.ai/pluggy-connect/v2.7.0/pluggy-connect.js"
ESPERA_S = 15 * 60  # o token de conexão vale 30 min; a página espera metade
# O widget chama `onSuccess` e logo `onClose`, e os dois avisos são assíncronos: o "fechou" pode
# chegar antes do ID. Depois dele, espera um pouco pelo ID antes de concluir "fechou sem conectar".
TOLERANCIA_S = 5.0
MAX_CORPO = 4096


def _para_js(valor) -> str:
    """JSON seguro dentro de `<script>`: `<` escapado, então `</script>` no valor não fecha a tag."""
    return json.dumps(valor).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def pagina(token: str, segredo: str) -> str:
    opcoes = {
        "connectToken": token,
        "includeSandbox": False,
        "connectorIds": [MEUPLUGGY],
        "selectedConnectorId": MEUPLUGGY,
    }
    base = "/" + segredo
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Viking · conectar banco</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem}}</style>
<script src="{html.escape(SCRIPT)}"></script></head>
<body>
<h1>Conectar um banco ao Viking</h1>
<p id="estado">Abrindo a janela da Pluggy… Escolha o banco dentro do Meu Pluggy e autorize.
Um banco por vez: para o próximo, rode o comando de novo.</p>
<script>
const base = {_para_js(base)};
const avisar = (rota, corpo) => fetch(base + rota, {{method: "POST", body: JSON.stringify(corpo)}});
const estado = (texto) => {{ document.getElementById("estado").textContent = texto; }};
const opcoes = Object.assign({_para_js(opcoes)}, {{
  onSuccess: (dados) => {{
    avisar("/ok", {{id: dados && dados.item && dados.item.id}});
    estado("Conectado. Pode fechar esta aba e voltar ao terminal.");
  }},
  onError: (erro) => {{
    avisar("/erro", {{mensagem: String((erro && erro.message) || erro)}});
    estado("A Pluggy devolveu um erro; veja o terminal.");
  }},
  onClose: () => {{ avisar("/fechou", {{}}); }},
}});
new PluggyConnect(opcoes).init();
</script>
</body></html>
"""


class Resultado:
    def __init__(self) -> None:
        self.item_id: str | None = None
        self.erro: str | None = None
        self.fechou = False
        self.pronto = threading.Event()  # qualquer aviso chegou
        self.tem_id = threading.Event()


def _manipulador(token: str, segredo: str, resultado: Resultado):
    base = "/" + segredo

    class Manipulador(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # o caminho tem o segredo: nada de log no terminal
            return

        def _responder(self, status: int, corpo: bytes = b"", tipo: str = "text/plain") -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):  # nome exigido pelo http.server
            if self.path != base:
                return self._responder(404)
            return self._responder(200, pagina(token, segredo).encode(), "text/html")

        def do_POST(self):  # nome exigido pelo http.server
            rota = self.path[len(base) :] if self.path.startswith(base + "/") else None
            if rota not in {"/ok", "/erro", "/fechou"}:
                return self._responder(404)
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > MAX_CORPO:
                return self._responder(413)
            try:
                dados = json.loads(self.rfile.read(tamanho) or b"{}")
            except ValueError:
                return self._responder(400)
            if rota == "/ok":
                try:
                    resultado.item_id = id_valido(
                        dados.get("id") if isinstance(dados, dict) else ""
                    )
                except EntradaInvalida:
                    return self._responder(400)
                resultado.tem_id.set()
            elif rota == "/erro":
                mensagem = dados.get("mensagem") if isinstance(dados, dict) else ""
                resultado.erro = str(mensagem or "erro sem mensagem")[:200]
            else:
                resultado.fechou = True
            self._responder(204)
            resultado.pronto.set()

    return Manipulador


def servir(
    token: str, *, abrir=None, espera_s: float = ESPERA_S, tolerancia_s: float = TOLERANCIA_S
) -> Resultado:
    """Serve a página em 127.0.0.1 (porta livre), abre no navegador e espera o widget responder."""
    segredo = secrets.token_urlsafe(24)
    resultado = Resultado()
    servidor = HTTPServer(("127.0.0.1", 0), _manipulador(token, segredo, resultado))
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/{segredo}"
        if abrir is None:
            import webbrowser

            abrir = webbrowser.open
        abrir(url)
        resultado.pronto.wait(espera_s)
        if resultado.fechou and resultado.item_id is None and resultado.erro is None:
            resultado.tem_id.wait(tolerancia_s)
    finally:
        servidor.shutdown()
        servidor.server_close()
    return resultado
