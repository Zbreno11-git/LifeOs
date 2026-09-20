# Life OS Arduino Fail Test

> **STATUS: PAUSADO (2026-09-20).** Esta trilha (dispositivo de pulso, controle local de PC) não é a
> prioridade atual do projeto — foi substituída pela automação de navegador como mecanismo principal de
> execução. Código preservado como está; ver `docs/arquitetura/wristband-hardware-pausado.md` e
> `docs/arquitetura/viking-visao-e-arquitetura.md` para o contexto completo.

O botão no Arduino Uno R3 envia `BUTTON` pela Serial USB. Um script no Bosgame
(mini PC Windows 11) recebe esse evento e chama a ferramenta MCP local
`PowerShell` (do servidor Windows-MCP), alternando o mute do sistema. Não há
HTTP, Wi-Fi, nuvem ou modelo de linguagem.

> Este teste rodava originalmente contra o `mac-control-mcp` (macOS). Foi
> migrado para o Bosgame porque o `mac-control-mcp` exige macOS 14+ e o Mac
> disponível é um Ventura 13 (Intel, 2017) — sem caminho de atualização de SO.
> Ver `docs/diario-de-bordo.md` na raiz do projeto para o histórico da decisão.

## 1. Fork e preparação no Bosgame (Windows 11)

O fork já foi criado: https://github.com/Zbreno11-git/Windows-MCP (a partir de
[CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)). No
Bosgame, clone-o ao lado desta pasta (mesma raiz do repo `LifeOs`):

```powershell
git clone https://github.com/Zbreno11-git/Windows-MCP.git
```

Instale o `uv` (gerenciador de pacotes Python usado pelo Windows-MCP):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Teste o servidor a partir do clone:

```powershell
cd Windows-MCP
uv run windows-mcp serve
```

Ctrl+C para encerrar depois de ver que ele sobe sem erro. O script Python
desta pasta inicia esse mesmo comando sozinho via MCP (stdio) — não precisa
deixá-lo rodando à parte.

## 2. Botão e sketch

Com o Arduino desconectado, ligue uma perna do botão ao pino **D2** e a outra
ao **GND**. Na breadboard, use pernas de lados opostos do botão: duas pernas
do mesmo lado costumam estar ligadas permanentemente. Não há resistor externo;
o sketch usa `INPUT_PULLUP`. Envie
`arduino/button_serial/button_serial.ino` pelo Arduino IDE (Windows). Um
clique deve imprimir uma linha `BUTTON` a 115200 baud no Monitor Serial. Feche
o monitor antes de iniciar o script Python, pois a porta só pode ter um
leitor.

## 3. Python no Bosgame

No PowerShell, dentro desta pasta (`LifeOS Arduino Fail Test`):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install mcp pyserial
python pc\serial_mcp_bridge.py --simulate
```

`--simulate` testa a conexão MCP e alterna o mute uma vez, sem Arduino.
Depois conecte o Uno e descubra a porta no **Gerenciador de Dispositivos**
(Portas COM e LPT):

```powershell
python pc\serial_mcp_bridge.py --port COM5
```

Substitua `COM5` pela porta real. Se o clone do Windows-MCP não estiver na
pasta padrão (irmã de `LifeOs/`), defina `WINDOWS_MCP_DIR` com o caminho
absoluto antes de rodar o script.

## Resultado esperado

Cada clique causa uma única linha `BUTTON` e uma chamada MCP `PowerShell` que
alterna o mute do sistema (via `keybd_event`/`VK_VOLUME_MUTE`). Se o áudio não
mudar, leia a mensagem de erro exibida pelo script. O comando enviado é
registrado; a confirmação da ferramenta e o efeito percebido no Bosgame são
observações separadas.

Fontes: https://github.com/CursorTouch/Windows-MCP ;
https://modelcontextprotocol.io/docs/2026-07-28/develop/build-client
