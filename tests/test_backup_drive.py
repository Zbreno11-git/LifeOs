"""O Drive do backup (Sessão 11c, D63): uma pasta, arquivos que só se acumulam, e nada que apague.

O dublê (`tests/drive_falso.py`) responde as duas consultas que o módulo faz; o registro é o do
`viking.db` do teste. A régua que lê o código prende o escopo do módulo: só `create`, `list` e
`get_media` (resposta do dono, 2026-10-06: todas as cópias ficam).
"""

import ast
import json
from pathlib import Path

import httplib2
import pytest
from googleapiclient.errors import HttpError
from tests.drive_falso import DriveFalso

from lifeos import registro
from lifeos.backup import drive

ARQUIVO = drive.__file__
PROIBIDAS = {"delete", "update", "trash", "emptyTrash", "permissions", "copy", "untrash"}


@pytest.fixture
def falso(monkeypatch):
    dublê = DriveFalso()
    monkeypatch.setattr(drive, "_servico", lambda: dublê)
    return dublê


@pytest.fixture(autouse=True)
def _origem():
    token = registro.ORIGEM.set("agendador")
    yield
    registro.ORIGEM.reset(token)


def test_a_pasta_nasce_uma_vez_e_os_arquivos_se_acumulam(falso):
    primeiro = drive.subir("viking-backup-2026-10-07T0900Z.json", b"{}", {"lembretes": 0})
    segundo = drive.subir("viking-backup-2026-10-08T0900Z.json", b"{}", {"lembretes": 0})
    pastas = [a for a in falso.arquivos if a["mimeType"] == "application/vnd.google-apps.folder"]
    assert [p["name"] for p in pastas] == [drive.PASTA]
    assert [a["name"] for a in falso.de_backup()] == [primeiro.nome, segundo.nome]
    assert all(a["parents"] == [pastas[0]["id"]] for a in falso.de_backup())


def test_ultimo_e_o_mais_novo_e_nada_sem_pasta(falso):
    assert drive.ultimo() is None
    drive.subir("viking-backup-2026-10-07T0900Z.json", b"um", {})
    novo = drive.subir("viking-backup-2026-10-08T0900Z.json", b"dois", {})
    assert drive.ultimo() == novo
    assert drive.baixar(novo.id) == b"dois"


def test_subir_fica_no_registro(falso):
    arquivo = drive.subir("viking-backup-2026-10-07T0900Z.json", b"{}", {"lembretes": 3})
    (acao,) = registro.recentes()
    assert (acao.operacao, acao.estado, acao.origem) == ("backup.drive", "feita", "agendador")
    assert acao.parametros == {"arquivo": arquivo.nome, "lembretes": 3}
    assert acao.resultado == {"arquivo_id": arquivo.id, "bytes": 2}


@pytest.mark.parametrize(("status", "estado"), [(500, "incerta"), (403, "falhou")])
def test_falha_do_drive_e_incerta_so_quando_pode_ter_criado(falso, status, estado):
    falso.falhar_no_create = status
    with pytest.raises(drive.FalhaDoDrive, match=f"HTTP {status}"):
        drive.subir("viking-backup-2026-10-07T0900Z.json", b"{}", {})
    (acao,) = registro.recentes()
    assert acao.estado == estado
    assert falso.de_backup() == []


def test_o_erro_do_google_nao_ecoa_o_corpo():
    corpo = {"error": {"errors": [{"reason": "insufficientPermissions"}], "message": "123456789"}}
    exc = HttpError(httplib2.Response({"status": "403"}), json.dumps(corpo).encode())
    assert drive._descrever(exc) == "HTTP 403 (insufficientPermissions)"


def _chamadas_de_files(arvore: ast.AST) -> set[str]:
    return {
        no.func.attr
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and ast.unparse(no.func.value).endswith("files()")
    }


def test_o_modulo_do_drive_so_cria_lista_e_baixa():
    arvore = ast.parse(Path(ARQUIVO).read_text())
    assert _chamadas_de_files(arvore) == {"create", "list", "get_media"}
    nomes = {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}
    assert not nomes & PROIBIDAS


def test_a_regua_enxerga_uma_exclusao():
    """Sem isto, uma régua que não acha nada ficaria verde à toa."""
    arvore = ast.parse("def f(s):\n    s.files().delete(fileId='x').execute()\n")
    assert _chamadas_de_files(arvore) == {"delete"}


def test_so_o_modulo_do_drive_fala_com_o_drive():
    """Classe 6 (erros): outro caminho que sobe ao Drive escaparia da régua e do registro."""
    raiz = Path(drive.__file__).parents[1]
    fora = [
        str(p.relative_to(raiz))
        for p in raiz.rglob("*.py")
        if p != Path(ARQUIVO) and _chamadas_de_files(ast.parse(p.read_text()))
    ]
    assert fora == []


_SEM_O_EXTRA_NUVEM = """
import sys
class Bloqueia:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome == "google.cloud" or nome.startswith(("google.cloud.", "starlette")):
            raise ImportError("sem o extra nuvem: " + nome)
sys.meta_path.insert(0, Bloqueia())
from lifeos.backup import conferir, drive, formato, restaurar
from lifeos.nuvem import chat_cliente, cliente
print("ok")
"""


def test_o_backup_do_mac_abre_sem_o_extra_nuvem():
    """O Mac instala só `--extra dev`: o login, o `--conferir` e o `--restaurar` rodam lá."""
    import subprocess
    import sys

    saida = subprocess.run(
        [sys.executable, "-c", _SEM_O_EXTRA_NUVEM],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert saida.returncode == 0 and saida.stdout.strip() == "ok", saida.stderr[-500:]
