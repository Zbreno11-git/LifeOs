"""O caminho do desastre (Sessão 11c, D63): `viking backup --restaurar ARQUIVO [--executar]`, no
Mac.

Lê um arquivo de backup baixado do Drive e confere tudo (`formato.de_bytes`). Sem `--executar` é
um **ensaio**: conta quantos lembretes já estão na nuvem iguais, diferentes, e quantos faltam, e
não grava nada. Com `--executar`, copia para a nuvem pelo motor, em lotes: os lembretes pela rota
da migração (`/lembretes/importar`), as ações, os gastos e, desde a 13 (D66), os fatos da
memória por `/backup/importar`. **Nada sobrescreve**: o que já existe diferente é contado e fica
como está (o mais novo pode ser o certo). No fim, confere relendo: todo lembrete do arquivo tem de
estar na nuvem. Os fatos voltam sem vetor: o texto final manda rodar `viking memoria --reindexar`.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class NaoRestaurou(RuntimeError):
    """A conferência depois da cópia achou lembrete do arquivo fora da nuvem."""


@dataclass
class Relatorio:
    arquivo: str
    criado_em: datetime
    no_arquivo: dict[str, int]
    lembretes_iguais: int = 0
    lembretes_diferentes: int = 0
    lembretes_a_copiar: int = 0
    copiados: dict[str, int] = field(
        default_factory=lambda: {
            "lembretes": 0,
            "acoes": 0,
            "gastos": 0,
            "memoria": 0,
            "receitas": 0,
        }
    )
    ja_iguais: dict[str, int] = field(
        default_factory=lambda: {"acoes": 0, "gastos": 0, "memoria": 0, "receitas": 0}
    )
    ja_diferentes: dict[str, int] = field(
        default_factory=lambda: {"acoes": 0, "gastos": 0, "memoria": 0, "receitas": 0}
    )
    fatos_recusados: int = 0  # o filtro de hoje recusou (uma regra nova)
    receitas_recusadas: int = 0


def _lotes(itens: list, tamanho: int) -> list[list]:
    return [itens[i : i + tamanho] for i in range(0, len(itens), tamanho)]


def restaurar(caminho: Path, *, executar: bool) -> Relatorio:
    from lifeos.backup import formato
    from lifeos.nuvem import cliente
    from lifeos.reminders import transporte

    backup = formato.de_bytes(caminho.read_bytes())
    sessao = cliente.sessao_de_chat()
    nuvem = cliente.impressoes_dos_lembretes(sessao)
    relatorio = Relatorio(caminho.name, backup.criado_em, backup.contagens())
    for lembrete in backup.lembretes:
        na_nuvem = nuvem.get(str(lembrete.id))
        if na_nuvem is None:
            relatorio.lembretes_a_copiar += 1
        elif na_nuvem == transporte.impressao(lembrete):
            relatorio.lembretes_iguais += 1
        else:
            relatorio.lembretes_diferentes += 1
    if not executar:
        return relatorio

    for lote in _lotes(backup.lembretes, transporte.MAX_LOTE):
        resposta = cliente.importar_lembretes(sessao, [transporte.para_dict(r) for r in lote])
        relatorio.copiados["lembretes"] += len(resposta["criados"])
    pedidos: list[tuple[list, list, list, list]] = [
        (lote, [], [], []) for lote in _lotes(backup.acoes, formato.LOTE_DO_BACKUP)
    ]
    pedidos += [([], lote, [], []) for lote in _lotes(backup.gastos, formato.LOTE_DO_BACKUP)]
    pedidos += [([], [], lote, []) for lote in _lotes(backup.memoria, formato.LOTE_DO_BACKUP)]
    pedidos += [([], [], [], lote) for lote in _lotes(backup.receitas, formato.LOTE_DO_BACKUP)]
    for acoes, gastos, fatos, receitas in pedidos:
        contas = cliente.importar_do_backup(sessao, acoes, gastos, fatos, receitas)
        relatorio.copiados["acoes"] += int(contas["acoes"].get("criadas", 0))
        relatorio.copiados["gastos"] += int(contas["gastos"].get("criados", 0))
        colecoes = ["acoes", "gastos"]
        if fatos:
            relatorio.copiados["memoria"] += int(contas["memoria"].get("criados", 0))
            relatorio.fatos_recusados += int(contas["memoria"].get("recusados", 0))
            colecoes.append("memoria")
        if receitas:
            relatorio.copiados["receitas"] += int(contas["receitas"].get("criadas", 0))
            relatorio.receitas_recusadas += int(contas["receitas"].get("recusadas", 0))
            colecoes.append("receitas")
        for colecao in colecoes:
            relatorio.ja_iguais[colecao] += int(contas[colecao].get("iguais", 0))
            relatorio.ja_diferentes[colecao] += len(contas[colecao].get("diferentes", []))

    depois = cliente.impressoes_dos_lembretes(sessao)
    faltam = [r.id for r in backup.lembretes if str(r.id) not in depois]
    if faltam:
        raise NaoRestaurou(
            f"a conferência achou {len(faltam)} lembrete(s) do arquivo fora da nuvem; rode de "
            "novo (nada se duplica)"
        )
    return relatorio


def texto(r: Relatorio, *, executou: bool) -> str:
    n = r.no_arquivo
    linhas = [
        (
            f"📦 {r.arquivo} (de {r.criado_em:%Y-%m-%d %H:%M} UTC): {n['lembretes']} lembrete(s), "
            f"{n['acoes']} ação(ões), {n['gastos']} mês(es) de gastos, "
            f"{n.get('memoria', 0)} fato(s) da memória, {n.get('receitas', 0)} receita(s)."
        ),
        (
            f"☁️  Na nuvem antes: {r.lembretes_iguais} lembrete(s) iguais, "
            f"{r.lembretes_diferentes} diferentes (ficam como estão), {r.lembretes_a_copiar} "
            "faltando."
        ),
    ]
    if not executou:
        linhas.append(
            "Ensaio: nada foi copiado. Para restaurar de verdade: o mesmo comando com --executar."
        )
        return "\n".join(linhas)
    c = r.copiados
    linhas.append(
        f"✅ Restaurado: {c['lembretes']} lembrete(s), {c['acoes']} ação(ões) e {c['gastos']} "
        f"mês(es) criados; já estavam iguais {r.ja_iguais['acoes']} ação(ões) e "
        f"{r.ja_iguais['gastos']} mês(es); diferentes, mantidos: {r.ja_diferentes['acoes']} "
        f"ação(ões) e {r.ja_diferentes['gastos']} mês(es). Todos os lembretes conferidos."
    )
    if r.no_arquivo.get("memoria", 0):
        linhas.append(
            f"🧠 Memória: {c['memoria']} fato(s) criados, {r.ja_iguais['memoria']} já iguais, "
            f"{r.ja_diferentes['memoria']} diferentes (mantidos), {r.fatos_recusados} recusados "
            "pelo filtro de hoje. Os vetores voltam com: viking memoria --reindexar"
        )
    if r.no_arquivo.get("receitas", 0):
        linhas.append(
            f"📋 Receitas: {c['receitas']} criadas, {r.ja_iguais['receitas']} já iguais, "
            f"{r.ja_diferentes['receitas']} diferentes (mantidas), {r.receitas_recusadas} "
            "recusadas pelo filtro de hoje."
        )
    return "\n".join(linhas)
