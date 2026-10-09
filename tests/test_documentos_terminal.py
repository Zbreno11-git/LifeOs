"""`viking documentos` no Mac (Sessão 14, D68), com o cliente da nuvem falso.

As perguntas: o arquivo é conferido aqui antes de sair (extensão, tamanho antes de ler, UTF-8), e
só o nome sem a pasta vai ao motor? O texto do arquivo nunca aparece na tela, nem num erro? A lista,
o esquecer e o desfazer mostram o que o motor devolveu, limpo?
"""

import argparse

import pytest

from lifeos.documentos import cortes, terminal
from lifeos.nuvem import cliente

SENTINELA = "SENTINELA-DO-ARQUIVO"
ESC = chr(0x1B)
DOC = {
    "id": "3d4e5f6a-7b8c-4d9e-8f0a-1b2c3d4e5f6a",
    "nome": "treino.md",
    "tema": "treino",
    "n_trechos": 3,
    "estado": "aprendido",
    "ativo": True,
    "criado_em": "2026-10-09T15:00:00.000000+00:00",
    "aprendido_em": "2026-10-09T15:00:05.000000+00:00",
    "invalida_em": None,
    "substituido_por": None,
    "esquecido_em": None,
    "apagar_em": None,
}


def _args(**kw):
    base = {"aprender": None, "tema": None, "todos": False, "esquecer": None, "desfazer": None}
    return argparse.Namespace(**(base | kw))


@pytest.fixture
def nuvem(monkeypatch):
    pedidos = []

    def acao(nome, corpo):
        pedidos.append((nome, corpo))
        if nome == "aprender":
            return {"documento": DOC, "substituido": None}
        return {"documento": DOC | {"ativo": nome == "desfazer"}}

    monkeypatch.setattr(cliente, "acao_dos_documentos", acao)
    monkeypatch.setattr(cliente, "dos_documentos", lambda: [DOC])
    return pedidos


def test_aprender_manda_o_nome_sem_a_pasta_o_tema_e_o_texto(nuvem, tmp_path, capsys):
    arquivo = tmp_path / "pasta" / "treino.md"
    arquivo.parent.mkdir()
    arquivo.write_text(f"# Perna\n\n{SENTINELA}\n", encoding="utf-8")
    assert terminal.executar(_args(aprender=str(arquivo), tema="treino")) == 0
    ((acao, corpo),) = nuvem
    assert acao == "aprender"
    assert corpo == {"nome": "treino.md", "tema": "treino", "texto": f"# Perna\n\n{SENTINELA}\n"}
    saida = capsys.readouterr()
    assert (
        "📄 aprendi: 3d4e5f6a" in saida.out and "treino.md (tema treino, 3 trecho(s))" in saida.out
    )
    assert SENTINELA not in saida.out + saida.err


def test_aprender_que_substitui_diz_como_desfazer(monkeypatch, tmp_path, capsys):
    antigo = DOC | {"id": "5f6a7b8c-9d0e-4f1a-8b2c-3d4e5f6a7b8c"}
    monkeypatch.setattr(
        cliente, "acao_dos_documentos", lambda _n, _c: {"documento": DOC, "substituido": antigo}
    )
    arquivo = tmp_path / "treino.md"
    arquivo.write_text("texto", encoding="utf-8")
    assert terminal.executar(_args(aprender=str(arquivo), tema="treino")) == 0
    assert "viking documentos --desfazer 5f6a7b8c" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("nome", "conteudo", "tema", "motivo"),
    [
        ("notas.pdf", b"%PDF-1.7", "treino", "só arquivos .md ou .txt"),
        ("notas.md", b"%PDF\x00binario", "treino", "binário"),
        ("notas.md", "ação".encode("latin-1"), "treino", "UTF-8"),
        ("notas.md", b"texto", "!!!", "sem letras"),
    ],
)
def test_o_arquivo_e_conferido_antes_de_sair(nuvem, tmp_path, capsys, nome, conteudo, tema, motivo):
    arquivo = tmp_path / nome
    arquivo.write_bytes(conteudo)
    assert terminal.executar(_args(aprender=str(arquivo), tema=tema)) == 1
    assert nuvem == []
    assert motivo in capsys.readouterr().err


def test_o_tamanho_e_conferido_antes_de_ler(nuvem, tmp_path, monkeypatch, capsys):
    arquivo = tmp_path / "grande.md"
    arquivo.write_bytes(b"a" * (cortes.MAX_BYTES + 1))
    lidos = []
    original = type(arquivo).read_bytes
    monkeypatch.setattr(
        type(arquivo), "read_bytes", lambda self: lidos.append(self) or original(self)
    )
    assert terminal.executar(_args(aprender=str(arquivo), tema="t")) == 1
    assert lidos == [] and nuvem == []
    assert "mais de 1.000.000 bytes" in capsys.readouterr().err


def test_sem_tema_ou_tema_sozinho_recusam(nuvem, tmp_path, capsys):
    arquivo = tmp_path / "treino.md"
    arquivo.write_text("texto", encoding="utf-8")
    assert terminal.executar(_args(aprender=str(arquivo))) == 1
    assert terminal.executar(_args(tema="treino")) == 1
    assert nuvem == []
    erro = capsys.readouterr().err
    assert "diga o tema" in erro and "--tema só vale com --aprender" in erro


def test_arquivo_que_nao_existe(nuvem, tmp_path, capsys):
    assert terminal.executar(_args(aprender=str(tmp_path / "x.md"), tema="t")) == 1
    assert "não consegui ler o arquivo (FileNotFoundError)" in capsys.readouterr().err


def test_a_lista_mostra_os_ativos_e_o_todos_tambem_os_outros(monkeypatch, capsys):
    esquecido = DOC | {
        "id": "9e8d7c6b-5a49-4382-9172-6a5b4c3d2e1f",
        "nome": f"ve{ESC}[2Jlho.md",
        "ativo": False,
        "esquecido_em": "2026-10-09T16:00:00.000000+00:00",
        "apagar_em": "2026-11-08T16:00:00.000000+00:00",
    }
    pela_metade = DOC | {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
        "estado": "aprendendo",
        "ativo": False,
        "aprendido_em": None,
        "apagar_em": "2026-10-10T15:00:00.000000+00:00",
    }
    monkeypatch.setattr(cliente, "dos_documentos", lambda: [DOC, esquecido, pela_metade])
    assert terminal.executar(_args()) == 0
    so_ativos = capsys.readouterr().out
    assert "3d4e5f6a" in so_ativos and "9e8d7c6b" not in so_ativos
    assert terminal.executar(_args(todos=True)) == 0
    todos = capsys.readouterr().out
    assert "9e8d7c6b" in todos and "(esquecido; some em" in todos and ESC not in todos
    assert "não terminou de aprender" in todos


def test_lista_vazia(monkeypatch, capsys):
    monkeypatch.setattr(cliente, "dos_documentos", list)
    assert terminal.executar(_args()) == 0
    assert "Nenhum documento ativo" in capsys.readouterr().out


def test_esquecer_e_desfazer(nuvem, capsys):
    assert terminal.executar(_args(esquecer="3d4e5f6a")) == 0
    assert terminal.executar(_args(desfazer="3d4e5f6a")) == 0
    assert nuvem == [("esquecer", {"id": "3d4e5f6a"}), ("desfazer", {"id": "3d4e5f6a"})]
    saida = capsys.readouterr().out
    assert "🗑️ esquecido" in saida and "↩️ de volta" in saida


def test_o_erro_da_nuvem_sai_com_1(monkeypatch, capsys):
    def falha():
        raise cliente.ErroDaNuvem("a nuvem não respondeu")

    monkeypatch.setattr(cliente, "dos_documentos", falha)
    assert terminal.executar(_args()) == 1
    assert "❌ Nuvem: a nuvem não respondeu" in capsys.readouterr().err
