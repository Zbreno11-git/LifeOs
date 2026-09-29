"""O repo é público até a Sessão 10 (D50): nada que identifique a máquina do dono entra nele.

Em 2026-09-28 o nome de usuário do Mac estava em 3 linhas (`.env.example` e duas do diário),
copiado de saídas coladas pelo dono; saiu a pedido dele. Este teste impede que volte: um caminho
`/Users/<nome>` só passa com um nome de exemplo. O histórico do git ainda tem os 3 commits antigos
(reescrever exigiria force push); isso se resolve com o repo privado.
"""

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# O nome como o macOS o aceita (letras, números, `.`, `_`, `-`): um `/Users/<exemplo>`, uma
# f-string ou esta própria regex não são caminho de ninguém.
_CAMINHO_DO_MAC = re.compile(r"/Users/([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXEMPLOS = {"x", "voce", "usuario"}


def _versionados() -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return [RAIZ / nome for nome in saida.splitlines() if (RAIZ / nome).is_file()]


def test_nenhum_nome_de_usuario_do_mac_no_repo():
    achados = []
    for arquivo in _versionados():
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binário (o .docx histórico)
        for nome in _CAMINHO_DO_MAC.findall(texto):
            if nome.lower() not in _EXEMPLOS:
                achados.append(f"{arquivo.relative_to(RAIZ)}: /Users/{nome}")
    assert achados == []


def test_a_regua_enxerga_um_caminho_real():
    """Sem isto, uma regex que não casa nada ficaria verde à toa."""
    # Montado em partes: com o caminho escrito inteiro aqui, este arquivo reprovaria a si mesmo
    # (no VPS passou antes do commit só porque o `git ls-files` ainda não o via).
    assert _CAMINHO_DO_MAC.findall("VIKING_JEV_DIR=/Users/" + "fulano/jev") == ["fulano"]
    assert _CAMINHO_DO_MAC.findall("/Users/<seu-usuario>/jev") == []
