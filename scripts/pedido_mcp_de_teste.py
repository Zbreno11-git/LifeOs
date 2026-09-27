"""Teste ao vivo da Sessão 5 (C9): um "outro app" pede, pelo MCP, para apagar o evento de teste.

Roda o servidor MCP do Viking em memória, como um cliente de verdade (`fastmcp.Client`), procura
o evento "Teste Viking" e pede para apagá-lo. Nada deve mudar até o dono aprovar em
`viking aprovar`. Imprime só o estado e o título — nunca o ID do evento (o repo é público e a
saída é colada em conversa).

    python scripts/pedido_mcp_de_teste.py
"""

import asyncio

from fastmcp import Client

from lifeos.mcp_server.server import mcp

TITULO = "Teste Viking"


async def main() -> int:
    async with Client(mcp) as cliente:
        achados = await cliente.call_tool("viking_buscar_eventos", {"termo_busca": TITULO})
        eventos = [e for e in achados.structured_content["eventos"] if e["title"] == TITULO]
        if not eventos:
            print(f"Nenhum evento '{TITULO}' no calendário: crie um antes (no chat).")
            return 1
        pedido = await cliente.call_tool(
            "viking_apagar_evento",
            {"event_id": eventos[0]["id"], "titulo_esperado": TITULO},
            raise_on_error=False,
        )
        dados = pedido.structured_content
        print("pedido:", dados.get("estado") or dados.get("erro"), "·", TITULO)
        de_novo = await cliente.call_tool("viking_buscar_eventos", {"termo_busca": TITULO})
        restam = [e for e in de_novo.structured_content["eventos"] if e["title"] == TITULO]
        print("ainda no calendário:", len(restam))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
