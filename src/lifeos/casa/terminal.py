"""`viking casa`: preparar, conferir e servir a ponte de casa (D70), no laptop de casa.

- `--preparar` gera, **aqui**, o par da conta `viking-casa@` (a privada nunca sai deste laptop; o
  certificado `casa-publica.pem` é o que sobe, pelo `scripts/nuvem.py casa-chave` do VPS), a
  chave e o certificado do HTTPS da rede de casa, e o token do aparelho. Pergunta a conta, a URL do
  motor e o token do HA (o token, sem eco). Imprime só o que é público ou o que vai para o
  `segredos.h` do firmware, que fica fora do git;
- `--chave-id ID` grava o id da chave que o Google deu ao certificado (o `casa-chave` mostra);
- `--conferir` mede tudo sem gastar: a pasta fechada, o HA e o interruptor, o motor (`/voz/saude`)
  e o `aplay`;
- sem opção, serve: HTTPS na porta da configuração, para o aparelho.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import datetime as dt
import getpass
import ipaddress
import json
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from lifeos.casa import config

VALIDADE_DA_CONTA_DIAS = 365  # a rotação da chave da conta (o Google aceita sem limite aqui)
VALIDADE_DO_TLS_DIAS = 10 * 365  # o certificado fixado no aparelho: trocar = gravar o firmware
AVISAR_DIAS = 30  # o `--conferir` avisa antes de a chave da conta vencer (e a voz parar)


def _nome(cn: str):  # o tipo é do `cryptography`
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _certificado(chave, cn: str, dias: int, nomes=()):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    agora = dt.datetime.now(dt.UTC)
    construtor = (
        x509.CertificateBuilder()
        .subject_name(_nome(cn))
        .issuer_name(_nome(cn))
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - dt.timedelta(minutes=5))
        .not_valid_after(agora + dt.timedelta(days=dias))
    )
    if nomes:
        alternativos: list[x509.GeneralName] = []
        for nome in nomes:
            try:
                alternativos.append(x509.IPAddress(ipaddress.ip_address(nome)))
            except ValueError:
                alternativos.append(x509.DNSName(nome))
        construtor = construtor.add_extension(x509.SubjectAlternativeName(alternativos), False)
    return construtor.sign(chave, hashes.SHA256())


def gerar(base: Path, *, nomes: list[str], conta: str, motor_url: str, ha_url: str,
          ha_token: str, interruptor: str, porta: int) -> str:  # fmt: skip
    """Cria a pasta e todos os arquivos (nunca sobrescreve) e devolve o token do aparelho."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    if (base / config.ARQUIVO).exists():
        raise FileExistsError(f"{base} já está preparada: apague a pasta para começar de novo")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    base.chmod(0o700)
    sem_senha = serialization.NoEncryption()

    conta_chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    config.gravar_fechado(
        base / config.PRIVADA,
        conta_chave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, sem_senha
        ),
    )
    publica = _certificado(conta_chave, "viking-casa", VALIDADE_DA_CONTA_DIAS)
    config.gravar_fechado(base / config.PUBLICA, publica.public_bytes(serialization.Encoding.PEM))

    tls_chave = ec.generate_private_key(ec.SECP256R1())
    config.gravar_fechado(
        base / config.TLS_CHAVE,
        tls_chave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, sem_senha
        ),
    )
    tls = _certificado(tls_chave, nomes[0], VALIDADE_DO_TLS_DIAS, nomes)
    config.gravar_fechado(
        base / config.TLS_CERTIFICADO, tls.public_bytes(serialization.Encoding.PEM)
    )

    token = secrets.token_urlsafe(32)
    dados = {
        "conta": conta,
        "chave_id": "",
        "motor_url": motor_url,
        "ha_url": ha_url,
        "ha_token": ha_token,
        "interruptor": interruptor,
        "aparelho_token": token,
        "porta": porta,
    }
    config.gravar_fechado(base / config.ARQUIVO, json.dumps(dados, indent=2).encode())
    return token


def _perguntar(texto: str, padrao: str = "") -> str:
    resposta = input(f"{texto}{f' [{padrao}]' if padrao else ''}: ").strip()
    return resposta or padrao


def preparar(nomes_extra: list[str]) -> int:
    base = config.pasta()
    maquina = socket.gethostname()
    nomes = [f"{maquina}.local", maquina, *nomes_extra]
    print("Preparando a ponte de casa em", base)
    conta = _perguntar("O e-mail da conta da casa (viking-casa@<projeto>.iam.gserviceaccount.com)")
    motor_url = _perguntar("A URL do motor (a VIKING_NUVEM_URL do .env do Mac)")
    ha_url = _perguntar("A URL do Home Assistant deste laptop", config.HA_PADRAO)
    ha_token = getpass.getpass("O token de longa duração do Home Assistant (não aparece): ").strip()
    interruptor = _perguntar("O interruptor da voz no HA", config.INTERRUPTOR_PADRAO)
    if not (conta.startswith("viking-casa@") and motor_url.startswith("https://") and ha_token):
        print("❌ a conta tem de ser a viking-casa@, a URL https://, e o token não pode ser vazio")
        return 1
    try:
        token = gerar(
            base,
            nomes=nomes,
            conta=conta,
            motor_url=motor_url,
            ha_url=ha_url,
            ha_token=ha_token,
            interruptor=interruptor,
            porta=config.PORTA_PADRAO,
        )
    except FileExistsError as exc:
        print(f"❌ {exc}")
        return 1
    tls = (base / config.TLS_CERTIFICADO).read_text()
    # O ESP32 nem sempre resolve um nome `.local` (o mDNS do firmware não está ligado): com um
    # `--nome` (o IP fixo do laptop, reservado no roteador), é ele que vai ao firmware.
    host = nomes_extra[0] if nomes_extra else nomes[0]
    aviso_do_host = (
        ""
        if nomes_extra
        else (
            "   (se o aparelho não achar o laptop por esse nome: --preparar de novo, numa pasta\n"
            "    nova, com --nome <o IP fixo do laptop>, e use o IP aqui)\n"
        )
    )
    print(
        f"\n✅ pronto. Próximos passos:\n"
        f"1. Copie para o Mac (ou o VPS) o certificado público da conta (só ele; a privada fica):\n"
        f"   {base / config.PUBLICA}\n"
        f"   e lá: python scripts/nuvem.py casa-chave casa-publica.pem --executar\n"
        f"2. Depois: viking casa --chave-id <o id que o casa-chave mostrar>\n"
        f"3. No src/segredos.h do firmware (fora do git), além da sua Wi-Fi:\n"
        f'   #define PONTE_HOST "{host}"\n'
        f"{aviso_do_host}"
        f"   #define PONTE_PORTA {config.PORTA_PADRAO}\n"
        f'   #define APARELHO_TOKEN "{token}"\n'
        f'   static const char PONTE_CERTIFICADO[] = R"PEM(\n{tls})PEM";\n'
    )
    return 0


def gravar_chave_id(chave_id: str) -> int:
    base = config.pasta()
    cfg = config.carregar(base)
    if not chave_id.isalnum() or len(chave_id) < 16:
        print("❌ o id da chave é o hexadecimal comprido que o casa-chave mostra")
        return 1
    arquivo = cfg.caminho(config.ARQUIVO)
    dados = json.loads(arquivo.read_text()) | {"chave_id": chave_id}
    novo = arquivo.with_suffix(".novo")
    novo.unlink(missing_ok=True)  # o de uma tentativa que caiu no meio
    config.gravar_fechado(novo, json.dumps(dados, indent=2).encode())
    novo.replace(arquivo)
    print("✅ o id da chave gravado")
    return 0


def dias_da_chave(certificado: Path, agora: dt.datetime | None = None) -> int:
    """Quantos dias faltam para o certificado da conta vencer (o Google recusa a chave depois)."""
    from cryptography import x509

    validade = x509.load_pem_x509_certificate(certificado.read_bytes()).not_valid_after_utc
    return (validade - (agora or dt.datetime.now(dt.UTC))).days


def _montar(cfg: config.Config):  # a ponte, com as dependências de verdade
    import requests

    from lifeos.casa import remoto
    from lifeos.casa.ha import HA
    from lifeos.casa.ponte import Ponte
    from lifeos.casa.som import Tocador

    motor = remoto.Motor(cfg.motor_url, remoto.sessao(cfg.credencial(), cfg.motor_url))
    ha = HA(cfg.ha_url, cfg.ha_token, cfg.interruptor, requests.Session())
    return motor, ha, Ponte(motor, ha, Tocador().tocar)


def conferir() -> int:
    """Mede sem gastar: nenhum áudio vai ao modelo."""
    try:
        cfg = config.carregar()
    except (config.ConfigInsegura, OSError, ValueError) as exc:
        print(f"❌ configuração: {exc}")
        return 1
    print("✅ a pasta e os arquivos fechados (700/600)")
    falhas = 0 if cfg.chave_id else 1
    print("✅ o id da chave gravado" if cfg.chave_id else "❌ falta `viking casa --chave-id ID`")
    dias = dias_da_chave(cfg.caminho(config.PUBLICA))
    if dias < 0:
        print("❌ a chave da conta venceu: gere outra (--preparar numa pasta nova) e suba")
        falhas += 1
    elif dias < AVISAR_DIAS:
        print(f"⚠️ a chave da conta vence em {dias} dias: gere outra e suba antes")
    else:
        print(f"✅ a chave da conta vale por mais {dias} dias")
    motor, ha, _ponte = _montar(cfg)
    interruptor = ha.ligado()
    print(
        "✅ o interruptor da voz está ligado"
        if interruptor.ligado
        else f"⬜ interruptor: {interruptor.motivo}"
    )
    try:
        saude = motor.saude()
        print(f"✅ o motor aceita a casa (commit {saude.get('commit', '?')})")
    except Exception as exc:  # noqa: BLE001 - o que deu errado, sem segredo
        print(f"❌ motor: {exc}")
        falhas += 1
    if shutil.which("aplay") is None:
        print("❌ falta o aplay: sudo apt install alsa-utils")
        falhas += 1
    else:
        placas = subprocess.run(["aplay", "-l"], capture_output=True, text=True, check=False)
        tem = "card" in placas.stdout
        print("✅ o aplay vê uma placa de som" if tem else "❌ o aplay não vê placa de som")
        falhas += 0 if tem else 1
    return 1 if falhas else 0


def servir() -> int:
    import logging

    import uvicorn

    from lifeos.casa import servidor

    try:
        cfg = config.carregar()
    except (config.ConfigInsegura, OSError, ValueError) as exc:
        print(f"❌ configuração: {exc}", file=sys.stderr)
        return 1
    if not cfg.chave_id:
        print("❌ falta `viking casa --chave-id ID` (depois do casa-chave no VPS)", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    _motor, _ha, ponte = _montar(cfg)
    uvicorn.run(
        servidor.app(ponte, cfg.aparelho_token),
        host="0.0.0.0",  # a rede de casa; nada é encaminhado para fora
        port=cfg.porta,
        ssl_keyfile=str(cfg.caminho(config.TLS_CHAVE)),
        ssl_certfile=str(cfg.caminho(config.TLS_CERTIFICADO)),
        access_log=False,
        log_level="warning",
    )
    return 0
