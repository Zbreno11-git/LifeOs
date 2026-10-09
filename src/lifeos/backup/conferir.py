"""A prova real do backup (Sessão 11c, D63): `viking backup --conferir`, no Mac.

Baixa o último arquivo do Drive, restaura num `viking.db` **novo, vazio e temporário** (o real
não é tocado: `banco.CAMINHO` é trocado só dentro de `banco_temporario`) e confere duas coisas:

1. **a restauração:** o que se lê de volta do banco vazio é igual ao arquivo (cada lembrete pela
   impressão, cada ação campo a campo). Os gastos não têm tabela no SQLite: só se conferem no
   arquivo (o Firestore os restaura, provado no emulador);
2. **o arquivo contra a nuvem de agora:** cada lembrete do arquivo está na nuvem igual, ou mudou
   **depois** do backup (concluído, enviado), e cada lembrete da nuvem está no arquivo ou nasceu
   depois dele. O resto (diferente sem ter mudado depois, sumido da nuvem, faltando no arquivo) é
   **divergência**, e a CLI sai com 1.

Não grava nada na nuvem nem no Drive. A saída tem só contagens (é colada em conversa).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


class SemBackup(RuntimeError):
    """A pasta do Drive ainda não tem backup."""


@dataclass
class Relatorio:
    arquivo: str
    criado_em: datetime
    no_arquivo: dict[str, int]
    restaurados: dict[str, int] = field(default_factory=dict)
    iguais: int = 0
    mudaram_depois: int = 0
    novos_depois: int = 0
    divergentes: int = 0  # diferentes na nuvem sem ter mudado depois do backup
    sumiram: int = 0  # no arquivo e não na nuvem (nada apaga lembrete)
    faltaram: int = 0  # na nuvem antes do backup e não no arquivo

    @property
    def restaurou_tudo(self) -> bool:
        return self.restaurados == self.no_arquivo

    @property
    def certo(self) -> bool:
        return self.restaurou_tudo and not (self.divergentes or self.sumiram or self.faltaram)


@contextmanager
def banco_temporario() -> Iterator[Path]:
    """Um `viking.db` novo num diretório temporário, só dentro do bloco; o real fica intocado."""
    from lifeos import banco

    with tempfile.TemporaryDirectory(prefix="viking-conferir-") as pasta:
        real = banco.CAMINHO
        banco.CAMINHO = Path(pasta) / "viking.db"
        try:
            yield banco.CAMINHO
        finally:
            banco.CAMINHO = real


def _restaurar_no_vazio(backup) -> dict[str, int]:
    """Grava o backup no banco temporário e conta o que voltou **igual** na releitura."""
    from lifeos import registro_sqlite
    from lifeos.reminders import onde, store, transporte

    if onde.estado() is not None or store.todos():
        raise RuntimeError("o banco temporário não nasceu vazio: nada foi conferido")
    for lembrete in backup.lembretes:
        store.importar(lembrete)
    for acao in backup.acoes:
        registro_sqlite.importar(acao)
    do_arquivo = {str(r.id): transporte.impressao(r) for r in backup.lembretes}
    relidos = {str(r.id): transporte.impressao(r) for r in store.todos()}
    acoes = registro_sqlite.exportar(desde=datetime.min.replace(tzinfo=UTC))
    return {
        "lembretes": sum(1 for i, imp in relidos.items() if do_arquivo.get(i) == imp),
        "acoes": sum(1 for a in acoes if a in backup.acoes),
        "gastos": len(backup.gastos),
        # A memória (Sessão 13) mora só na nuvem: conferida no arquivo (`formato.ler`), como os
        # gastos; o banco do Mac não a guarda.
        "memoria": len(backup.memoria),
        "receitas": len(backup.receitas),  # a 13b (D67): também só na nuvem
        "documentos": len(backup.documentos),  # a 14 (D68): também só na nuvem
        "trechos": len(backup.trechos),
    }


def conferir() -> Relatorio:
    from lifeos.backup import drive, formato
    from lifeos.nuvem import cliente
    from lifeos.reminders import transporte

    arquivo = drive.ultimo()
    if arquivo is None:
        raise SemBackup("a pasta do Drive ainda não tem backup")
    backup = formato.de_bytes(drive.baixar(arquivo.id))
    relatorio = Relatorio(arquivo.nome, backup.criado_em, backup.contagens())
    with banco_temporario():
        relatorio.restaurados = _restaurar_no_vazio(backup)

    nuvem = cliente.estado_dos_lembretes(cliente.sessao_de_chat())
    no_arquivo = {str(r.id): transporte.impressao(r) for r in backup.lembretes}
    for lembrete_id, impressao in no_arquivo.items():
        if lembrete_id not in nuvem:
            relatorio.sumiram += 1
        elif nuvem[lembrete_id].impressao == impressao:
            relatorio.iguais += 1
        elif nuvem[lembrete_id].mudou_em > backup.criado_em:
            relatorio.mudaram_depois += 1
        else:
            relatorio.divergentes += 1
    for lembrete_id, estado in nuvem.items():
        if lembrete_id in no_arquivo:
            continue
        if estado.criado_em > backup.criado_em:
            relatorio.novos_depois += 1
        else:
            relatorio.faltaram += 1
    return relatorio


def texto(r: Relatorio) -> str:
    linhas = [
        f"📦 Backup conferido: {r.arquivo} (de {r.criado_em:%Y-%m-%d %H:%M} UTC).",
        (
            f"🗄️  Restaurado num banco vazio: {r.restaurados.get('lembretes', 0)} de "
            f"{r.no_arquivo['lembretes']} lembrete(s), {r.restaurados.get('acoes', 0)} de "
            f"{r.no_arquivo['acoes']} ação(ões); {r.no_arquivo['gastos']} mês(es) de gastos e "
            f"{r.no_arquivo.get('memoria', 0)} fato(s) e {r.no_arquivo.get('receitas', 0)} "
            f"receita(s) da memória e {r.no_arquivo.get('documentos', 0)} documento(s) "
            f"({r.no_arquivo.get('trechos', 0)} trecho(s)) conferidos no arquivo (a memória e "
            "os documentos moram só na nuvem)."
        ),
        (
            f"☁️  Contra a nuvem de agora: {r.iguais} iguais, {r.mudaram_depois} mudaram depois "
            f"do backup, {r.novos_depois} criados depois."
        ),
    ]
    if r.certo:
        linhas.append("✅ O backup restaura inteiro e bate com a nuvem.")
    else:
        linhas.append(
            f"❌ Divergências: {r.divergentes} diferentes sem mudança depois do backup, "
            f"{r.sumiram} sumiram da nuvem, {r.faltaram} faltaram no backup"
            + ("" if r.restaurou_tudo else "; e a restauração não voltou inteira")
            + "."
        )
    return "\n".join(linhas)
