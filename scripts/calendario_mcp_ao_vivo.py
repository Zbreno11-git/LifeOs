"""Teste ao vivo da Sessão 3b (fechado na 8b): as tools de calendário do MCP contra a agenda real.

Roda o servidor MCP do Viking em memória, como um cliente de verdade (`fastmcp.Client`):
1. cria o evento de dia inteiro "Teste Viking 3b" na data dada;
2. lista os eventos dessa data e confere que ele veio como dia inteiro, no dia certo;
3. busca pelo título (e mostra se a lista veio completa);
4. PEDE para apagar: nada some até o dono aprovar em `viking aprovar`.

    python scripts/calendario_mcp_ao_vivo.py AAAA-MM-DD
    python scripts/calendario_mcp_ao_vivo.py AAAA-MM-DD --conferir

A data é a que o dono escolhe: um evento de dia inteiro é uma data, não um instante, então não
depende de fuso. Imprime estado, título e data, nunca o ID do evento (o repo é público e a saída
é colada em conversa). Saída: 0 = tudo como esperado; 1 = algo diferente (a linha diz o quê).
"""

import argparse
import asyncio
import sys
from datetime import date

from fastmcp import Client

from lifeos.mcp_server.server import mcp

TITULO = "Teste Viking 3b"


async def _do_dia(cliente, data: str) -> list[dict]:
    resposta = await cliente.call_tool(
        "viking_listar_eventos_por_data", {"data_inicio": data}, raise_on_error=False
    )
    if resposta.is_error:
        raise RuntimeError(f"listar por data falhou: {resposta.structured_content}")
    return [e for e in resposta.structured_content["eventos"] if e["title"] == TITULO]


async def conferir(cliente, data: str) -> int:
    restam = await _do_dia(cliente, data)
    print(f"ainda no calendário em {data}: {len(restam)}")
    return 0 if not restam else 1


async def rodar(cliente, data: str) -> int:
    if await _do_dia(cliente, data):
        print(f"Já existe um '{TITULO}' em {data}: apague antes (ou rode com --conferir).")
        return 1

    criado = await cliente.call_tool(
        "viking_criar_evento_dia_inteiro", {"summary": TITULO, "data": data}, raise_on_error=False
    )
    if criado.is_error:
        print(f"1. criar: FALHOU · {criado.structured_content.get('erro')}")
        return 1
    print(f"1. criar: ok · dia inteiro: {criado.structured_content['all_day']}")

    do_dia = await _do_dia(cliente, data)
    certos = [e for e in do_dia if e["all_day"] and e["start"] == data]
    print(f"2. listar por data: {len(do_dia)} achado(s) · dia inteiro em {data}: {len(certos)}")

    busca = await cliente.call_tool(
        "viking_buscar_eventos", {"termo_busca": TITULO}, raise_on_error=False
    )
    achados = [e for e in busca.structured_content.get("eventos", []) if e["title"] == TITULO]
    print(
        f"3. buscar: {len(achados)} achado(s) · completa: {busca.structured_content.get('completa')}"
    )

    if len(certos) != 1:
        print(
            "Esperava exatamente 1 evento de dia inteiro nessa data: parei antes de pedir apagar."
        )
        return 1
    pedido = await cliente.call_tool(
        "viking_apagar_evento",
        {"event_id": certos[0]["id"], "titulo_esperado": TITULO},
        raise_on_error=False,
    )
    estado = pedido.structured_content.get("estado") or pedido.structured_content.get("erro")
    print(f"4. pedido de apagar: {estado}")
    print(
        f"Agora: confira '{TITULO}' no Google Calendar em {data} (dia inteiro); depois "
        "`viking aprovar`; depois rode de novo com --conferir."
    )
    return 0 if estado == "aguardando_aprovacao" else 1


async def main(argv: list[str]) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("data", help="AAAA-MM-DD, um dia futuro")
    leitor.add_argument("--conferir", action="store_true", help="só conta os que restam")
    args = leitor.parse_args(argv)
    try:
        data = date.fromisoformat(args.data).isoformat()
    except ValueError:
        print(f"Data inválida: {args.data!r} (use AAAA-MM-DD).")
        return 1
    async with Client(mcp) as cliente:
        return await (conferir(cliente, data) if args.conferir else rodar(cliente, data))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
