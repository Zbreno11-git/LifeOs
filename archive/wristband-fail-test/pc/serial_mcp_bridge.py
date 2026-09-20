"""Ponte local Arduino Serial -> cliente MCP -> Windows-MCP (fork local).

Sem HTTP, nuvem, IA ou comandos arbitrários enviados pela porta Serial.
A acao executada e fixa: alterna o mute do sistema a cada BUTTON recebido,
via a ferramenta MCP `PowerShell` do Windows-MCP.
"""

import argparse
import asyncio
import os
from pathlib import Path

import serial
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

# VK_VOLUME_MUTE = 0xAD; keybd_event com dwFlags=0 (key down) e 2 (KEYEVENTF_KEYUP).
# Chave de midia global do Windows: funciona independente da janela em foco.
TOGGLE_MUTE_COMMAND = """
Add-Type -Language CSharp -TypeDefinition @"
using System.Runtime.InteropServices;
public class LifeOsKeys {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, System.UIntPtr dwExtraInfo);
}
"@
[LifeOsKeys]::keybd_event(0xAD, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 50
[LifeOsKeys]::keybd_event(0xAD, 0, 2, [UIntPtr]::Zero)
"""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Porta do Uno, ex.: COM5")
    parser.add_argument("--simulate", action="store_true", help="Faz uma chamada sem Arduino")
    args = parser.parse_args()
    if not args.simulate and not args.port:
        parser.error("informe --port ou use --simulate")

    default_dir = Path(__file__).resolve().parents[2] / "windows-mcp"
    windows_mcp_dir = Path(os.environ.get("WINDOWS_MCP_DIR", default_dir)).expanduser()
    if not windows_mcp_dir.is_dir():
        parser.error(f"clone do fork Windows-MCP nao encontrado: {windows_mcp_dir} (defina WINDOWS_MCP_DIR)")

    params = StdioServerParameters(
        command="uv",
        args=["--directory", str(windows_mcp_dir), "run", "windows-mcp", "serve"],
    )
    async with Client(stdio_client(params)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        if "PowerShell" not in tools:
            raise RuntimeError(
                f"o servidor MCP nao expos a ferramenta PowerShell; disponiveis: {sorted(tools)}"
            )
        print("MCP conectado; ferramenta PowerShell disponivel.")

        async def press() -> None:
            result = await client.call_tool("PowerShell", {"command": TOGGLE_MUTE_COMMAND})
            if result.is_error:
                print(f"Falha no MCP: {result.content}")
                return
            print(f"Botao recebido; mute alternado. Resultado: {result.content}")

        if args.simulate:
            await press()
            return

        with serial.Serial(args.port, 115200, timeout=0.2) as board:
            # Abrir a Serial costuma reiniciar o Uno. Ignoramos dados desse intervalo.
            await asyncio.sleep(2)
            board.reset_input_buffer()
            print(f"Aguardando botao em {args.port}. Encerre com Ctrl+C.")
            while True:
                line = (await asyncio.to_thread(board.readline)).decode("utf-8", errors="replace").strip()
                if line == "BUTTON":
                    await press()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Encerrado.")
