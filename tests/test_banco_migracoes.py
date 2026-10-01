"""As migrations do `viking.db` (Sessão 9, D56): o banco que o dono tem hoje migra sem perder
nada; rodar de novo não muda nada; uma falha no meio deixa o banco como estava; um banco mais novo
que o código não abre; e o backup de antes existe.

O banco "de hoje" é o de `tests/banco_antigo.py`: o DDL literal de `5d0ace4`, com dados. O banco
de teste sempre começa vazio e o de produção nunca (skill `testes-que-provam` §6): por isso quase
todo teste aqui parte de um banco cheio.
"""

import hashlib
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from tests import banco_antigo

from lifeos import banco

TABELAS = ("reminders", "acoes", "confirmacoes", "lembretes_na_nuvem")
IGUAIS = ("acoes", "confirmacoes")  # a migração 5 reconstrói `reminders` (id novo): ver abaixo
_CONTEUDO = (
    "type, title, body, tags, due_at, completed_at, source, external_id, metadata, created_at, "
    "updated_at"
)
_INSTANTES = {4, 5, 9, 10}  # due_at, completed_at, created_at, updated_at, na ordem de _CONTEUDO


def _migradas(antes: dict[str, list[tuple]]) -> dict[str, list[tuple]]:
    """As linhas de antes, como ficam depois das migrações: a 6 (Sessão 10c) acrescenta a coluna
    `erros` às confirmações, zerada; nenhum outro valor muda."""
    return {**antes, "confirmacoes": [(*linha, 0) for linha in antes["confirmacoes"]]}


def _lembretes(caminho) -> list[tuple]:
    """Os lembretes pelo conteúdo, sem o id: a migração 5 troca o inteiro por UUID e reescreve os
    instantes em largura fixa. Cada instante volta como `datetime`: o mesmo instante em dois
    formatos é igual, e um instante trocado não é."""
    conn = sqlite3.connect(caminho)
    try:
        linhas = conn.execute(f"SELECT {_CONTEUDO} FROM reminders ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [
        tuple(
            datetime.fromisoformat(v) if i in _INSTANTES and v is not None else v
            for i, v in enumerate(linha)
        )
        for linha in linhas
    ]


@pytest.fixture
def antigo():
    """O `banco.CAMINHO` deste teste, no formato de `5d0ace4`, com dados."""
    return banco_antigo.criar(banco.CAMINHO)


def _abrir() -> None:
    with banco.conectar():
        pass


def _ledger(caminho) -> list[tuple]:
    conn = sqlite3.connect(caminho)
    try:
        return conn.execute(
            "SELECT numero, nome, checksum FROM migracoes ORDER BY numero"
        ).fetchall()
    finally:
        conn.close()


# --- o banco de hoje migra ------------------------------------------------------------------


def test_banco_de_hoje_migra_sem_perder_nem_mudar_nenhuma_linha(antigo):
    antes = {t: banco_antigo.linhas(antigo, t) for t in IGUAIS}
    lembretes = _lembretes(antigo)
    assert [len(v) for v in (lembretes, *antes.values())] == [4, 4, 3]  # o fixture tem o que diz

    _abrir()

    assert {t: banco_antigo.linhas(antigo, t) for t in IGUAIS} == _migradas(antes)
    assert _lembretes(antigo) == lembretes
    assert [n for n, _nome, _c in _ledger(antigo)] == [m.numero for m in banco.MIGRACOES]


def test_migracao_5_da_um_uuid4_por_lembrete_e_instantes_de_largura_fixa(antigo):
    import uuid

    _abrir()

    conn = sqlite3.connect(antigo)
    linhas = conn.execute(
        "SELECT id, due_at, completed_at, created_at, updated_at, enviado_em, envio_estado, "
        "envio_reservado_por, envio_reservado_ate FROM reminders"
    ).fetchall()
    conn.close()
    ids = [linha[0] for linha in linhas]
    assert len(set(ids)) == len(ids) == 4
    assert all(uuid.UUID(i).version == 4 for i in ids)
    instantes = [v for linha in linhas for v in linha[1:5] if v is not None]
    assert len(instantes) == 11  # 4 criados + 4 atualizados + 2 prazos + 1 concluído
    assert {len(v) for v in instantes} == {len("2026-09-25T15:00:00.000000+00:00")}
    assert all(v.endswith("+00:00") for v in instantes)
    assert {linha[5:] for linha in linhas} == {(None, None, None, None)}


def test_migrar_duas_vezes_nao_muda_nada(antigo):
    _abrir()
    depois_da_primeira = banco_antigo.despejo(antigo)
    assert len(_ledger(antigo)) == len(banco.MIGRACOES)  # a primeira aplicou de verdade

    _abrir()

    assert banco_antigo.despejo(antigo) == depois_da_primeira


def _esquema(caminho) -> dict[str, tuple]:
    conn = sqlite3.connect(caminho)
    try:
        tabelas = [
            n
            for (n,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            t: (
                conn.execute(f"PRAGMA table_info({t})").fetchall(),
                sorted((i[1], i[2]) for i in conn.execute(f"PRAGMA index_list({t})").fetchall()),
            )
            for t in sorted(tabelas)
        }
    finally:
        conn.close()


def test_banco_novo_e_banco_antigo_migrado_tem_o_mesmo_formato(tmp_path, monkeypatch):
    antigo = banco_antigo.criar(tmp_path / "antigo.db")
    monkeypatch.setattr(banco, "CAMINHO", antigo)
    _abrir()
    novo = tmp_path / "novo.db"
    monkeypatch.setattr(banco, "CAMINHO", novo)
    _abrir()

    assert _esquema(novo) == _esquema(antigo)
    assert set(_esquema(novo)) == {"migracoes", *TABELAS}


def test_banco_de_antes_da_sessao_2_ganha_prazo_em_utc(monkeypatch):
    """A migração 2 era o `user_version` 1 dos lembretes: um prazo sem fuso, gravado antes da
    Sessão 2, é o horário do fuso configurado. Com o `user_version` 0."""
    caminho = banco_antigo.criar(banco.CAMINHO, user_version=0)
    conn = sqlite3.connect(caminho)
    conn.execute("UPDATE reminders SET due_at = '2026-09-25T14:00:00' WHERE title = 'Dentista'")
    conn.commit()
    conn.close()
    monkeypatch.setattr("lifeos.config.TIMEZONE", ZoneInfo("America/Sao_Paulo"))

    _abrir()

    prazos = dict(
        sqlite3.connect(caminho).execute("SELECT title, due_at FROM reminders").fetchall()
    )
    assert prazos["Dentista"] == "2026-09-25T17:00:00.000000+00:00"  # 14h em -03:00
    assert prazos["Pagar luz"] == "2026-09-25T15:00:00.000000+00:00"  # já em UTC: o mesmo


# --- falha no meio, banco mais novo, migração editada ---------------------------------------


def _com_uma_migracao_que_falha(monkeypatch, passo) -> None:
    proxima = max(m.numero for m in banco.MIGRACOES) + 1
    monkeypatch.setattr(
        banco, "MIGRACOES", (*banco.MIGRACOES, banco.Migracao(proxima, "falha de teste", passo))
    )


def test_falha_no_meio_de_um_banco_de_hoje_deixa_o_banco_como_estava(antigo, monkeypatch):
    """As 1–4 e a que falha estão pendentes juntas: nada delas fica, nem o ledger."""
    antes = banco_antigo.despejo(antigo)
    _com_uma_migracao_que_falha(
        monkeypatch,
        (
            "CREATE TABLE meio (x)",
            "ALTER TABLE reminders ADD COLUMN meio TEXT",
            "INSERT INTO tabela_que_nao_existe VALUES (1)",
        ),
    )

    with pytest.raises(sqlite3.OperationalError, match="tabela_que_nao_existe"):
        _abrir()

    assert banco_antigo.despejo(antigo) == antes


def test_falha_numa_funcao_depois_de_escrever_desfaz_a_escrita(antigo, monkeypatch):
    _abrir()
    antes = banco_antigo.despejo(antigo)

    def escreve_e_falha(conn):
        conn.execute("UPDATE reminders SET title = 'estragado'")
        conn.execute("DELETE FROM acoes")
        raise RuntimeError("falhou no meio")

    _com_uma_migracao_que_falha(monkeypatch, escreve_e_falha)

    with pytest.raises(RuntimeError, match="falhou no meio"):
        _abrir()

    assert banco_antigo.despejo(antigo) == antes


def test_banco_migrado_por_versao_mais_nova_nao_abre(antigo):
    _abrir()
    conn = sqlite3.connect(antigo)
    conn.execute("INSERT INTO migracoes VALUES (99, 'do futuro', 'x', '2027-01-01')")
    conn.commit()
    conn.close()
    antes = banco_antigo.despejo(antigo)

    with pytest.raises(banco.BancoMaisNovo, match="migração 99") as erro:
        _abrir()

    assert "git pull" in str(erro.value)
    assert banco_antigo.despejo(antigo) == antes


def test_migracao_editada_depois_de_aplicada_nao_abre(antigo):
    _abrir()
    conn = sqlite3.connect(antigo)
    conn.execute("UPDATE migracoes SET checksum = 'outro' WHERE numero = 2")
    conn.commit()
    conn.close()

    with pytest.raises(banco.MigracaoAlterada, match="migração 2"):
        _abrir()


# Os checksums das migrations já publicadas, escritos à mão. Uma migração publicada não se edita
# (nem o comentário: o checksum de uma função é o código-fonte dela). Se este teste cair, desfaça
# a mudança e crie a migração seguinte; uma migração nova entra aqui no commit que a publica.
PUBLICADAS = {
    1: "685f07dd7b5d7f7d9559a1b7c0e1f7937709f9d710f76dc9beec3f25984dacce",
    2: "b312c7afc06be46621a376696be5b2438bd2befff8a0b7327d0fff6f32b247ef",
    3: "38ad6a5da0e26b2acf1314aba0485842302656df3004259a2cea9ba7806d2924",
    4: "1684c0620d7745e7e85c8956b7a61d3da67af915068580aabc9b8408b0e8cbe5",
    5: "674966561ed3b66c5e6307acc97edb3bdaf1a2bc8182804a8db75e5fba0fdc76",
    6: "d5342cd47e86be7612b88a44da0c92ab40af2a195a46bab6096637716f20141d",
    7: "4d04ef2b0f83d3dd04166b087fda20a17613c00e6633984fbd1a31ba40ce9173",
}


def test_migracoes_publicadas_nao_mudaram():
    assert {m.numero: m.checksum for m in banco.MIGRACOES} == PUBLICADAS


def test_numeros_em_sequencia_desde_1():
    assert [m.numero for m in banco.MIGRACOES] == list(range(1, len(banco.MIGRACOES) + 1))


# --- backup -----------------------------------------------------------------------------------


def test_backup_antes_de_migrar_um_banco_com_dados(antigo):
    antes = banco_antigo.despejo(antigo)

    _abrir()

    copia = banco.caminho_do_backup(1)
    assert banco_antigo.despejo(copia) == antes
    assert [p.name for p in antigo.parent.iterdir() if p.name.endswith(".parcial")] == []


def test_backup_nao_se_repete_nem_se_sobrescreve(antigo):
    _abrir()
    copia = banco.caminho_do_backup(1)
    mtime = copia.stat().st_mtime_ns
    _abrir()
    assert copia.stat().st_mtime_ns == mtime
    assert sorted(p.name for p in antigo.parent.iterdir() if "antes-da-migracao" in p.name) == [
        copia.name
    ]


def test_banco_novo_nao_gera_backup():
    _abrir()
    assert [p.name for p in banco.CAMINHO.parent.iterdir() if "antes-da" in p.name] == []


# --- dois processos ---------------------------------------------------------------------------

_ABRE = """
from lifeos import banco
with banco.conectar() as conn:
    print(conn.execute("SELECT count(*) FROM migracoes").fetchone()[0])
"""


def test_processos_abrindo_juntos_um_banco_de_hoje(antigo):
    """Chat, MCP e `viking aprovar` podem abrir ao mesmo tempo depois do `git pull`: todos abrem,
    e cada migração entra uma vez. Processos de verdade: uma thread passaria pela trava do próprio
    processo."""
    antes = {t: banco_antigo.linhas(antigo, t) for t in IGUAIS}
    lembretes = _lembretes(antigo)
    ambiente = {**os.environ, "VIKING_DB_PATH": str(antigo)}
    processos = [
        subprocess.Popen(
            [sys.executable, "-c", _ABRE],
            env=ambiente,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    saidas = [p.communicate(timeout=60) for p in processos]

    assert [p.returncode for p in processos] == [0] * 4, [e for _o, e in saidas]
    assert [o.strip() for o, _e in saidas] == [str(len(banco.MIGRACOES))] * 4
    assert [n for n, _nome, _c in _ledger(antigo)] == [m.numero for m in banco.MIGRACOES]
    assert {t: banco_antigo.linhas(antigo, t) for t in IGUAIS} == _migradas(antes)
    assert _lembretes(antigo) == lembretes
    assert banco.caminho_do_backup(1).exists()


def test_o_checksum_e_do_texto_da_migracao():
    """A régua acima só vale se o checksum muda quando o texto muda."""
    m = banco.Migracao(1, "x", ("CREATE TABLE a (x)",))
    assert m.checksum == hashlib.sha256(b"CREATE TABLE a (x)").hexdigest()
    assert banco.Migracao(1, "x", ("CREATE TABLE a (y)",)).checksum != m.checksum


def test_ledger_guarda_quando_em_utc(antigo):
    _abrir()
    conn = sqlite3.connect(antigo)
    (quando,) = conn.execute("SELECT aplicada_em FROM migracoes WHERE numero = 1").fetchone()
    conn.close()
    assert datetime.fromisoformat(quando).utcoffset() == UTC.utcoffset(None)


# --- o que o dono vê --------------------------------------------------------------------------


def test_viking_com_banco_mais_novo_diz_o_que_fazer_e_sai_com_1(antigo, monkeypatch, capsys):
    """Qualquer subcomando abre o banco antes de fazer algo: a migração (e o backup) acontece no
    primeiro `viking` depois do `git pull`, e um banco mais novo vira uma linha, não um traceback
    no meio do chat. A mensagem não leva o caminho inteiro (no Mac, tem o nome do usuário)."""
    from lifeos import cli

    _abrir()
    conn = sqlite3.connect(antigo)
    conn.execute("INSERT INTO migracoes VALUES (99, 'do futuro', 'x', '2027-01-01')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(sys, "argv", ["viking", "registro"])

    with pytest.raises(SystemExit) as saida:
        cli.main()

    assert saida.value.code == 1
    erro = capsys.readouterr().err
    assert "migração 99" in erro and "git pull" in erro
    assert str(antigo.parent) not in erro


def test_primeiro_viking_depois_do_pull_migra_e_faz_o_backup(antigo, monkeypatch):
    from lifeos import cli

    monkeypatch.setattr(sys, "argv", ["viking", "registro"])
    with pytest.raises(SystemExit):
        cli.main()

    assert len(_ledger(antigo)) == len(banco.MIGRACOES)
    assert banco.caminho_do_backup(1).exists()


# --- a corrida, sem depender de sorte ---------------------------------------------------------
# O teste dos processos acima quase nunca sobrepõe as migrações (sobem com dezenas de ms de
# diferença; migrar leva poucos ms): a rodada de mutações da Sessão 9 mostrou as duas regras
# abaixo vivas com ele verde. Estes dois forçam a corrida com uma conexão que intercepta o BEGIN.


def _conexao_com_gancho(caminho, gancho_antes=None, gancho_depois=None):
    class ComGancho(sqlite3.Connection):
        def execute(self, sql, *args):
            eh_begin = sql.lstrip().upper().startswith("BEGIN")
            if eh_begin and gancho_antes:
                gancho_antes()
            resultado = super().execute(sql, *args)
            if eh_begin and gancho_depois:
                gancho_depois()
            return resultado

    conn = sqlite3.connect(caminho, isolation_level=None, factory=ComGancho)
    conn.row_factory = sqlite3.Row
    return conn


def _migrar_por_outra_conexao(caminho) -> None:
    outra = sqlite3.connect(caminho, isolation_level=None)
    outra.row_factory = sqlite3.Row
    try:
        banco.migrar(outra)
    finally:
        outra.close()


def test_outro_processo_migra_entre_a_leitura_e_a_trava(antigo):
    """Leu o ledger sem trava (pendentes), e antes do BEGIN outro processo migrou tudo: depois da
    trava o ledger é relido, e nada é aplicado de novo."""
    conn = _conexao_com_gancho(antigo, gancho_antes=lambda: _migrar_por_outra_conexao(antigo))
    try:
        banco.migrar(conn)
    finally:
        conn.close()

    assert [n for n, _nome, _c in _ledger(antigo)] == [m.numero for m in banco.MIGRACOES]


def test_a_trava_de_escrita_vem_no_begin(antigo):
    """Logo depois do BEGIN, ninguém mais consegue a trava de escrita: com um BEGIN que só lê
    (DEFERRED), outro processo leria o mesmo ledger e os dois tentariam migrar."""
    tentativas = []

    def outro_tenta_escrever():
        outra = sqlite3.connect(antigo, isolation_level=None, timeout=0)
        try:
            outra.execute("BEGIN IMMEDIATE")
            outra.execute("ROLLBACK")
            tentativas.append("conseguiu")
        except sqlite3.OperationalError as exc:
            tentativas.append(str(exc))
        finally:
            outra.close()

    conn = _conexao_com_gancho(antigo, gancho_depois=outro_tenta_escrever)
    try:
        banco.migrar(conn)
    finally:
        conn.close()

    assert tentativas == ["database is locked"]
