# FastMCP

- **Projeto:** https://github.com/jlowin/fastmcp
- **O que é:** framework Python para expor funções como tools de um servidor MCP (`@mcp.tool()`),
  com geração automática de schema a partir de tipos/anotações e docstring.
- **Versão pinada:** 4.0.5 (junto com `mcp==2.2.0`).
- **Papel no projeto:** `src/lifeos/mcp_server/server.py` usa FastMCP para expor calendário e
  lembretes como tools MCP, consumíveis por Claude Desktop e outros agentes.

## Testar tools em memória, sem stdio nem subprocesso

`fastmcp.Client` aceita o próprio objeto `FastMCP` (não só uma URL/transporte) e conecta em
memória — dá pra chamar `list_tools()`/`call_tool()` pelo protocolo real (mesma validação de
schema, mesmo formato de resposta de um cliente de verdade) sem subir processo nenhum:

```python
import asyncio
from fastmcp import Client
from lifeos.mcp_server.server import mcp


async def chamar():
    async with Client(mcp) as client:
        return await client.call_tool("viking_criar_lembrete", {"titulo": "Teste"})


resultado = asyncio.run(chamar())
```

Não precisa de `pytest-asyncio`/`pytest-anyio`: `asyncio.run()` dentro de uma função de teste comum
(síncrona) já funciona, inclusive reusando o mesmo objeto `mcp` (singleton do módulo) entre várias
chamadas de `asyncio.run()` em testes diferentes — cada uma cria e destrói seu próprio loop, sem
erro de "Future attached to a different loop" (testado em 2026-09-20, ver `tests/test_mcp_server.py`).

## `ToolResult`: texto humano + payload estruturado na mesma resposta

Por padrão, o retorno de uma tool vira só o texto/JSON em `.content`. Para separar "texto para
humano" de "dado estável para quem consome" (a mesma tool pode servir os dois), retorne um
`fastmcp.tools.ToolResult`:

```python
from fastmcp.tools import ToolResult


@mcp.tool()
def minha_tool(x: int) -> ToolResult:
    return ToolResult(content="Feito.", structured_content={"x": x})
```

`content` vira o texto normal (idêntico ao que uma `str` pura geraria — aditivo, não quebra cliente
que só lê texto); `structured_content` (um `dict`) fica disponível em `CallToolResult.structured_content`
e em `.data`, sem precisar que o consumidor faça parsing de string.

**Achado que vira armadilha:** `ToolResult(is_error=True)` faz `Client.call_tool()` **levantar uma
exceção `ToolError`** por padrão, em vez de devolver um resultado inspecionável — é assim que o MCP
sinaliza "a ferramenta falhou de verdade" para o chamador. Um teste que queira inspecionar o
`ToolResult` de um caminho de erro (texto + `structured_content`) sem capturar a exceção precisa
passar `raise_on_error=False` em `call_tool()`.

## Limite conhecido

Quando a anotação de retorno é `ToolResult` (um wrapper genérico, não um tipo específico), FastMCP
não anuncia um `output_schema` formal para a tool — `structured_content` existe na resposta, mas o
cliente não vê de antemão o formato esperado. Uma tool que retornasse um tipo de domínio próprio
(dataclass/pydantic model) em vez de `str`/`ToolResult` teria schema anunciado; não foi o desenho
escolhido para lembretes (ver `sessoes.md`, Sessão 3) para não acoplar o formato de saída do MCP ao
modelo interno (`Reminder`) mais do que o necessário.
