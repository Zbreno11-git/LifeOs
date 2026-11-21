"""A configuração da ponte de casa: uma pasta só do usuário que roda a ponte (D70).

Tudo que é segredo ou dado do dono mora em `~/.config/viking-casa/` (ou `VIKING_CASA_PASTA`),
nunca no repositório público: o e-mail da conta (que tem o ID do projeto), a URL do motor, o token
do Home Assistant, o token do aparelho, a chave privada da conta e a do HTTPS. A pasta é 700 e cada
arquivo 600, e a ponte **recusa** abrir se estiverem mais abertos (outro usuário do laptop leria a
chave que fala com o Viking inteiro).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARQUIVO = "casa.json"
PRIVADA = "casa-privada.pem"  # a chave da conta viking-casa@: nunca sai do laptop
PUBLICA = "casa-publica.pem"  # o certificado dela: o único que sobe ao Google (`casa-chave`)
TLS_CHAVE = "tls-chave.pem"  # o HTTPS da ponte na rede de casa
TLS_CERTIFICADO = "tls-certificado.pem"  # vai fixado no firmware do aparelho
TOKEN_URI = "https://oauth2.googleapis.com/token"
INTERRUPTOR_PADRAO = "input_boolean.viking_voz"
HA_PADRAO = "http://127.0.0.1:8123"
PORTA_PADRAO = 8765
CAMPOS = (
    "conta",  # o e-mail da viking-casa@
    "chave_id",  # o id da chave depois do `casa-chave` (vazio até lá)
    "motor_url",
    "ha_url",
    "ha_token",
    "interruptor",
    "aparelho_token",
    "porta",
)


class ConfigInsegura(RuntimeError):
    """A pasta ou um arquivo dela está aberto para outros usuários, ou falta algo."""


def pasta() -> Path:
    return Path(os.getenv("VIKING_CASA_PASTA", "~/.config/viking-casa")).expanduser()


def _fechado(caminho: Path, esperado: int) -> None:
    modo = stat.S_IMODE(caminho.stat().st_mode)
    if modo & 0o077:
        raise ConfigInsegura(
            f"{caminho} está com permissão {oct(modo)}: outros usuários deste computador leem. "
            f"Rode `chmod {oct(esperado)[2:]} {caminho}`"
        )


@dataclass(frozen=True)
class Config:
    conta: str
    chave_id: str
    motor_url: str
    ha_url: str
    ha_token: str
    interruptor: str
    aparelho_token: str
    porta: int
    base: Path

    def caminho(self, nome: str) -> Path:
        return self.base / nome

    def credencial(self) -> dict[str, Any]:
        """A informação de conta de serviço que o `google-auth` lê, montada aqui (a chave privada
        nasceu neste laptop; o Google só tem o certificado)."""
        return credencial(self.conta, self.chave_id, self.caminho(PRIVADA).read_text())


def credencial(conta: str, chave_id: str, privada_pem: str) -> dict[str, Any]:
    return {
        "type": "service_account",
        "client_email": conta,
        "private_key_id": chave_id,
        "private_key": privada_pem,
        "token_uri": TOKEN_URI,
    }


def carregar(base: Path | None = None) -> Config:
    """A configuração conferida: a pasta 700, cada arquivo 600, e todos os campos."""
    base = base or pasta()
    arquivo = base / ARQUIVO
    if not arquivo.exists():
        raise ConfigInsegura(f"falta {arquivo}: rode `viking casa --preparar`")
    _fechado(base, 0o700)
    for nome in (ARQUIVO, PRIVADA, TLS_CHAVE):
        _fechado(base / nome, 0o600)
    dados = json.loads(arquivo.read_text())
    faltam = [c for c in CAMPOS if c not in dados or (c != "chave_id" and dados[c] in ("", None))]
    if faltam:
        raise ConfigInsegura(f"{arquivo} sem: {', '.join(faltam)}")
    return Config(
        conta=str(dados["conta"]),
        chave_id=str(dados["chave_id"]),
        motor_url=str(dados["motor_url"]).rstrip("/"),
        ha_url=str(dados["ha_url"]).rstrip("/"),
        ha_token=str(dados["ha_token"]),
        interruptor=str(dados["interruptor"]),
        aparelho_token=str(dados["aparelho_token"]),
        porta=int(dados["porta"]),
        base=base,
    )


def gravar_fechado(caminho: Path, conteudo: bytes) -> None:
    """Cria o arquivo já com 600 (nunca existe um instante aberto) e recusa sobrescrever."""
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "wb") as saida:
        saida.write(conteudo)
