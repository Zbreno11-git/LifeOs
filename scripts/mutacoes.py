"""Mutações curadas: o teste dos testes das regras que decidem apagar, acessar e o que sai da máquina.

Cada `Mutacao` é o defeito que uma regra do Viking impede, escrito como troca de texto, com o
teste que TEM de cair. Se ele não cai, o teste não protege a regra — mesmo verde. Roda à mão, não
no `pytest` nem no CI (skill `testes-que-provam`, `referencia/mutacao.md`):

    python scripts/mutacoes.py              # todas
    python scripts/mutacoes.py freio        # só as que têm "freio" no nome

Garantias, cada uma com o incidente que a ensinou (no projeto de origem das skills):
- todas as âncoras casam EXATAMENTE uma vez, conferidas antes de rodar qualquer mutação;
- a mutação muda código, não comentário (tokens sem comentário antes × depois);
- partida verde: sem mutação, os testes-alvo passam, com zero pulados;
- cai o teste ESPERADO, não qualquer um;
- o arquivo volta byte a byte (`finally` + sha256), e o bytecode de cada rodada vai para um
  diretório descartável — um `.pyc` do código mutado nunca sobrevive à restauração;
- trava no disco (`.mutacao.lock`) enquanto roda: não edite nada durante uma rodada;
- sem timeout de propósito: um SIGTERM não passa pelo `finally` e deixaria código mutado.

Saída: 0 = todas mortas pelo teste esperado · 1 = alguma sobreviveu ou matou outro teste ·
2 = recusa antes de rodar (âncora, mutação inerte, partida vermelha, trava).
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import tokenize
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TRAVA = RAIZ / ".mutacao.lock"


@dataclass(frozen=True)
class Mutacao:
    nome: str
    arquivo: str
    velho: str
    novo: str
    esperado: str  # "tests/arquivo.py::nome_do_teste" (sem parâmetros)

    @property
    def arquivo_de_teste(self) -> str:
        return self.esperado.split("::")[0]


MUTACOES = [
    Mutacao(
        "calendário: título divergente apaga o evento",
        "src/lifeos/calendar/service.py",
        "    return chave(a) == chave(b)",
        "    return True",
        "tests/test_calendar_tools.py::test_recusa_quando_o_titulo_nao_bate",
    ),
    Mutacao(
        "calendário: título esperado vazio passa da primeira trava",
        "src/lifeos/calendar/service.py",
        "    if not titulo_esperado.strip():",
        "    if False:",
        "tests/test_calendar_tools.py::test_titulo_vazio_nao_apaga_evento_de_titulo_em_branco",
    ),
    Mutacao(
        "mcp: recusa de calendário volta como sucesso",
        "src/lifeos/mcp_server/server.py",
        '            structured_content={"erro": resposta.erro.codigo, **resposta.erro.dados},\n'
        "            is_error=True,",
        '            structured_content={"erro": resposta.erro.codigo, **resposta.erro.dados},\n'
        "            is_error=False,",
        "tests/test_mcp_server.py::test_apagar_titulo_divergente_pelo_mcp_nao_apaga",
    ),
    Mutacao(
        "bloqueio: subdomínio de banco escapa",
        "src/lifeos/browser/_redacao.py",
        'if host == dominio or host.endswith("." + dominio):',
        "if host == dominio:",
        "tests/test_redacao.py::test_dominio_bloqueado",
    ),
    Mutacao(
        "bloqueio: URL inicial bloqueada abre o subprocesso",
        "src/lifeos/browser/jev_runner.py",
        "    if bloqueado:\n        return _erro(",
        "    if False:\n        return _erro(",
        "tests/test_browser_seguranca.py::test_url_inicial_bloqueada_nao_abre_subprocesso",
    ),
    Mutacao(
        "envelope: domínio bloqueado sai para o OpenRouter",
        "src/lifeos/browser/_jev_subprocess.py",
        "        _checar(page)\n        decisao = choose(",
        "        decisao = choose(",
        "tests/test_jev_subprocess_main.py::test_dominio_bloqueado_na_pagina_inicial_nao_sai_nada",
    ),
    Mutacao(
        "envelope: página sai sem redação para o OpenRouter",
        "src/lifeos/browser/_jev_subprocess.py",
        "decisao = choose(_redacao.pagina(page), goal, history)",
        "decisao = choose(page, goal, history)",
        "tests/test_jev_subprocess_main.py::test_choose_recebe_pagina_redigida_e_estado_fica_intacto",
    ),
    Mutacao(
        "freio: envelope não confere a decisão",
        "src/lifeos/browser/_jev_subprocess.py",
        "        _frear(page, decisao)\n",
        "",
        "tests/test_jev_subprocess_main.py::test_clique_em_sair_e_recusado_antes_de_executar",
    ),
    Mutacao(
        "freio: página sem guards passa em vez de recusar",
        "src/lifeos/browser/_jev_subprocess.py",
        "        if not isinstance(guards, dict):",
        "        if False:",
        "tests/test_jev_subprocess_main.py::test_layout_de_guards_diferente_recusa_navegar",
    ),
    Mutacao(
        "freio: link de logout só com ícone passa",
        "src/lifeos/browser/_acoes_sensiveis.py",
        "    if categoria is None and _href_de_sair(href):",
        "    if False:",
        "tests/test_acoes_sensiveis.py::test_link_de_sair_so_com_icone",
    ),
    Mutacao(
        "freio: caractere invisível disfarça o rótulo",
        "src/lifeos/browser/_acoes_sensiveis.py",
        "unicodedata.category(c) in _INVISIVEIS",
        "False",
        "tests/test_acoes_sensiveis.py::test_disfarce_nao_escapa_do_freio",
    ),
    Mutacao(
        "freio: opção de select que envia no change passa",
        "src/lifeos/browser/_acoes_sensiveis.py",
        'JULGADAS = frozenset({"click", "select"})',
        'JULGADAS = frozenset({"click"})',
        "tests/test_acoes_sensiveis.py::test_opcao_perigosa_de_select_e_recusada",
    ),
    Mutacao(
        "freio: 'Excluir' genérico no diálogo de excluir conta passa",
        "src/lifeos/browser/_acoes_sensiveis.py",
        "        if any(r.search(escopo) for r in _CONTA_REGRAS):",
        "        if False:",
        "tests/test_acoes_sensiveis.py::test_excluir_generico_num_dialogo_de_excluir_conta",
    ),
    Mutacao(
        "delimitador: a página fecha o bloco de não confiável",
        "src/lifeos/nao_confiavel.py",
        '    return texto.replace("«", "‹").replace("»", "›")',
        "    return texto",
        "tests/test_browser_seguranca.py::test_um_unico_bloco_delimitado_e_a_injecao_fica_dentro",
    ),
    Mutacao(
        "redação: CPF sem dígito verificador vira [CPF]",
        "src/lifeos/browser/_redacao.py",
        "        if soma * 10 % 11 % 10 != int(d[n]):",
        "        if False:",
        "tests/test_redacao.py::test_numero_sem_digito_verificador_valido_fica",
    ),
    Mutacao(
        "config: timeout NaN desliga o prazo do navegador",
        "src/lifeos/config.py",
        "    if not math.isfinite(valor):",
        "    if False:",
        "tests/test_config.py::test_float_env_rejeita_nan_e_infinito",
    ),
    Mutacao(
        "gmail: token de outro escopo passa como válido",
        "src/lifeos/google_auth.py",
        "    if token_path.exists() and set(scopes) <= _escopos_do_arquivo(token_path):",
        "    if token_path.exists():",
        "tests/test_google_auth.py::test_token_de_outro_escopo_abre_login_em_vez_de_passar_como_valido",
    ),
    Mutacao(
        "login: token revogado vira beco sem saída",
        "src/lifeos/google_auth.py",
        "        except RefreshError:\n",
        "        except ZeroDivisionError:\n",
        "tests/test_google_auth.py::test_renovacao_recusada_vira_login_novo_e_nao_beco_sem_saida",
    ),
    Mutacao(
        "gmail: permissão desmarcada no login vira token gravado",
        "src/lifeos/google_auth.py",
        "        if faltando:",
        "        if False:",
        "tests/test_google_auth.py::test_permissao_desmarcada_no_login_falha_alto_e_nao_grava_token",
    ),
    Mutacao(
        "gmail: token gravado legível por outros usuários",
        "src/lifeos/google_auth.py",
        "    os.chmod(token_path, 0o600)",
        "    os.chmod(token_path, 0o644)",
        "tests/test_google_auth.py::test_token_gravado_so_legivel_pelo_dono",
    ),
    Mutacao(
        "gmail: conteúdo sai sem redação para o Gemini",
        "src/lifeos/gmail/tools.py",
        "    return bloco(_DADOS_DOS_EMAILS, _redigido(conteudo))",
        "    return bloco(_DADOS_DOS_EMAILS, conteudo)",
        "tests/test_gmail_tools.py::test_corpo_redigido_como_pagina",
    ),
    Mutacao(
        "gmail: token de link no corpo passa",
        "src/lifeos/gmail/tools.py",
        '_URL.sub(lambda m: _redacao.redigir_url(m.group()), _redacao.redigir(texto or ""))',
        '_redacao.redigir(texto or "")',
        "tests/test_gmail_tools.py::test_corpo_redigido_como_pagina",
    ),
    Mutacao(
        "gmail: e-mail fora do bloco de não confiável",
        "src/lifeos/gmail/tools.py",
        "    return bloco(_DADOS_DOS_EMAILS, _redigido(conteudo))",
        "    return _redigido(conteudo)",
        "tests/test_gmail_tools.py::test_injecao_no_corpo_fica_dentro_do_bloco",
    ),
    Mutacao(
        "gmail: e-mail que falhou no lote some em silêncio",
        "src/lifeos/gmail/service.py",
        "    return [_email_de(lidos[i]) for i in ids if i in lidos], len(pendentes)",
        "    return [_email_de(lidos[i]) for i in ids if i in lidos], 0",
        "tests/test_gmail_service.py::test_quem_falha_sempre_e_contado_nunca_somido",
    ),
    Mutacao(
        "gmail: raio-x no teto se passa por total",
        "src/lifeos/gmail/service.py",
        "return ids[:limite], bool(pagina) or len(ids) > limite",
        "return ids[:limite], False",
        "tests/test_gmail_service.py::test_raio_x_no_teto_avisa_que_e_piso",
    ),
    Mutacao(
        "gmail: enchimento invisível da prévia vai para o Gemini",
        "src/lifeos/gmail/service.py",
        'if c != "\\u034f" and unicodedata.category(c) != "Cf"',
        "if True",
        "tests/test_gmail_service.py::test_enchimento_invisivel_da_previa_some",
    ),
    Mutacao(
        "gmail: ID estranho chega na API",
        "src/lifeos/gmail/service.py",
        "    if not _ID.fullmatch(email_id):",
        "    if False:",
        "tests/test_gmail_service.py::test_id_estranho_e_recusado_antes_da_api",
    ),
    Mutacao(
        "gmail: caractere de controle do corpo chega ao modelo",
        "src/lifeos/gmail/service.py",
        "    corpo = limpar_controles(corpo)",
        "    corpo = corpo",
        "tests/test_gmail_service.py::test_corpo_com_controle_sai_limpo",
    ),
    Mutacao(
        "limpeza: estrela/importante só na consulta do Gmail",
        "src/lifeos/gmail/service.py",
        "elif email.na_caixa and not email.estrela and not email.importante:",
        "elif email.na_caixa:",
        "tests/test_gmail_limpeza.py::test_protegidos_nunca_saem_nem_se_a_consulta_falhar",
    ),
    Mutacao(
        "limpeza: anexo sai se a consulta falhar",
        "src/lifeos/gmail/service.py",
        "candidatos = [i for i in reversed(candidatos) if i not in com_anexo]",
        "candidatos = list(reversed(candidatos))",
        "tests/test_gmail_limpeza.py::test_protegidos_nunca_saem_nem_se_a_consulta_falhar",
    ),
    Mutacao(
        "limpeza: remetente parecido entra",
        "src/lifeos/gmail/service.py",
        "            if email.endereco != endereco:",
        "            if False:",
        "tests/test_gmail_limpeza.py::test_remetente_parecido_nao_entra",
    ),
    Mutacao(
        "limpeza: operador de busca amplia a seleção",
        "src/lifeos/gmail/service.py",
        "        if not _ENDERECO.fullmatch(endereco):",
        "        if False:",
        "tests/test_gmail_limpeza.py::test_pedido_que_nao_e_endereco_exato_nao_consulta_nada",
    ),
    Mutacao(
        "arquivar: tira mais que o rótulo INBOX",
        "src/lifeos/gmail/service.py",
        'return _rotular(ids, {"removeLabelIds": ["INBOX"]})',
        'return _rotular(ids, {"removeLabelIds": ["INBOX", "UNREAD"]})',
        "tests/test_gmail_limpeza.py::test_arquivar_so_tira_o_rotulo_inbox",
    ),
    Mutacao(
        "limpeza: confirmação arquiva o que mudou desde a lista",
        "src/lifeos/gmail/limpeza.py",
        "    ids = [i for i in aprovados if i in ainda]",
        "    ids = list(aprovados)",
        "tests/test_gmail_limpeza.py::test_confirmacao_so_arquiva_o_que_foi_aprovado_e_ainda_vale",
    ),
    Mutacao(
        "desfazer: a mesma limpeza desfeita duas vezes",
        "src/lifeos/gmail/limpeza.py",
        '    if resultado.get("desfeito_em"):',
        "    if False:",
        "tests/test_gmail_limpeza.py::test_desfazer_devolve_exatamente_os_arquivados_uma_vez",
    ),
    Mutacao(
        "confirmação: código vencido aprova",
        "src/lifeos/confirmacao.py",
        '        if datetime.fromisoformat(linha["expira_em"]) < agora:',
        "        if False:",
        "tests/test_confirmacao.py::test_codigo_vencido_nao_aprova",
    ),
    Mutacao(
        "confirmação: proposta nova não invalida a velha",
        "src/lifeos/confirmacao.py",
        "    expira = agora + VALIDADE\n"
        "    with _sessao() as conn:\n"
        "        conn.execute(\n"
        "            \"UPDATE confirmacoes SET estado = 'substituida' WHERE",
        "    expira = agora + VALIDADE\n"
        "    with _sessao() as conn:\n"
        "        conn.execute(\n"
        "            \"UPDATE confirmacoes SET estado = 'aberta' WHERE",
        "tests/test_confirmacao.py::test_proposta_nova_invalida_o_codigo_velho",
    ),
    Mutacao(
        "confirmação: desfazer depois do prazo",
        "src/lifeos/confirmacao.py",
        "    if registro.consumida_em is None or registro.consumida_em + janela < agora:",
        "    if registro.consumida_em is None:",
        "tests/test_confirmacao.py::test_desfazer_acha_a_acao_feita_dentro_da_janela",
    ),
    Mutacao(
        "confirmação: dígito de outro alfabeto passa no formato",
        "src/lifeos/confirmacao.py",
        '_CODIGO = re.compile(rf"[0-9]{{{DIGITOS}}}")',
        '_CODIGO = re.compile(rf"\\d{{{DIGITOS}}}")',
        "tests/test_confirmacao.py::test_formato_errado_e_recusado",
    ),
    Mutacao(
        "aprovação: a linha com o código vai ao Gemini",
        "src/lifeos/assistant/agent.py",
        "        local = aprovacao_local(prompt)",
        "        local = None",
        "tests/test_gmail_aprovacao.py::test_laco_do_chat_nunca_manda_a_linha_de_aprovacao_ao_gemini",
    ),
    Mutacao(
        "aprovação: o código volta no texto do Gemini",
        "src/lifeos/gmail/tools.py",
        "        _SEM_CODIGO,\n    ]",
        "        _SEM_CODIGO + str(proposta.codigo),\n    ]",
        "tests/test_gmail_aprovacao.py::test_codigo_vai_ao_terminal_e_nunca_ao_gemini",
    ),
]


def _tokens_sem_comentario(fonte: str) -> list[tuple[int, str]]:
    ignorar = {tokenize.COMMENT, tokenize.NL}
    return [
        (t.type, t.string)
        for t in tokenize.generate_tokens(io.StringIO(fonte).readline)
        if t.type not in ignorar
    ]


def _recusas(mutacoes: list[Mutacao]) -> list[str]:
    recusas = []
    for m in mutacoes:
        caminho = RAIZ / m.arquivo
        if not caminho.is_file():
            recusas.append(f"{m.nome}: arquivo {m.arquivo} não existe")
            continue
        if not (RAIZ / m.arquivo_de_teste).is_file():
            recusas.append(f"{m.nome}: teste {m.arquivo_de_teste} não existe")
            continue
        fonte = caminho.read_text()
        vezes = fonte.count(m.velho)
        if vezes != 1:
            recusas.append(f"{m.nome}: âncora casa {vezes} vez(es) em {m.arquivo}, e não 1")
            continue
        mutado = fonte.replace(m.velho, m.novo)
        if _tokens_sem_comentario(mutado) == _tokens_sem_comentario(fonte):
            recusas.append(f"{m.nome}: mutação inerte (só muda comentário/espaço)")
    return recusas


def _pytest(arquivos: list[str], relatorio: Path, cache: Path) -> dict[str, set[str]]:
    """Roda os arquivos e devolve os nomes (sem parâmetros) que falharam e que foram pulados."""
    ambiente = {**os.environ, "PYTHONPYCACHEPREFIX": str(cache), "PYTHONDONTWRITEBYTECODE": "1"}
    comando = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header"]
    comando += [f"--junitxml={relatorio}", *arquivos]
    subprocess.run(comando, cwd=RAIZ, env=ambiente, capture_output=True, text=True, check=False)
    resultado = {"falhou": set(), "pulou": set(), "rodou": set()}
    for caso in ET.parse(relatorio).getroot().iter("testcase"):
        arquivo = caso.get("classname", "").replace(".", "/") + ".py"
        nome = f"{arquivo}::{caso.get('name', '').split('[')[0]}"
        resultado["rodou"].add(nome)
        if caso.find("failure") is not None or caso.find("error") is not None:
            resultado["falhou"].add(nome)
        elif caso.find("skipped") is not None:
            resultado["pulou"].add(nome)
    return resultado


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def main(filtros: list[str]) -> int:
    mutacoes = [m for m in MUTACOES if not filtros or any(f in m.nome for f in filtros)]
    if not mutacoes:
        print(f"nenhuma mutação casa com {filtros}")
        return 2
    if TRAVA.exists():
        print(f"RECUSADO: trava {TRAVA} existe ({TRAVA.read_text().strip()}). Uma rodada anterior")
        print("pode ter morrido deixando código mutado: rode `git status` antes de apagar a trava.")
        return 2

    recusas = _recusas(mutacoes)
    if recusas:
        print(f"RECUSADAS: {len(recusas)} (nenhuma mutação rodou)")
        for recusa in recusas:
            print(f"  - {recusa}")
        return 2

    TRAVA.write_text(f"pid {os.getpid()}\n")
    try:
        with tempfile.TemporaryDirectory(prefix="mutacao-") as tmp:
            tmp = Path(tmp)
            arquivos = sorted({m.arquivo_de_teste for m in mutacoes})
            partida = _pytest(arquivos, tmp / "partida.xml", tmp / "cache-partida")
            faltando = {m.esperado for m in mutacoes} - partida["rodou"]
            if partida["falhou"] or partida["pulou"] or faltando:
                print("RECUSADO: partida não está verde e completa, mutação nada provaria.")
                for rotulo, nomes in (
                    ("falhou", partida["falhou"]),
                    ("pulou", partida["pulou"]),
                    ("teste esperado não existe", faltando),
                ):
                    for nome in sorted(nomes):
                        print(f"  - {rotulo}: {nome}")
                return 2

            linhas, ruins = [], 0
            for i, m in enumerate(mutacoes, 1):
                caminho = RAIZ / m.arquivo
                original = caminho.read_bytes()
                antes = _sha(caminho)
                try:
                    caminho.write_text(original.decode().replace(m.velho, m.novo))
                    rodada = _pytest([m.arquivo_de_teste], tmp / f"m{i}.xml", tmp / f"cache-{i}")
                finally:
                    caminho.write_bytes(original)
                if _sha(caminho) != antes:
                    print(f"ERRO GRAVE: {m.arquivo} não voltou byte a byte. Confira `git diff`.")
                    return 2
                if m.esperado in rodada["falhou"]:
                    linhas.append(f"  morta    {m.nome}")
                    continue
                ruins += 1
                if rodada["falhou"]:
                    outros = ", ".join(sorted(rodada["falhou"]))
                    linhas.append(f"  OUTRO    {m.nome} — caiu {outros}, não {m.esperado}")
                else:
                    linhas.append(f"  VIVA     {m.nome} — nenhum teste caiu")
            print(
                f"mutações: {len(mutacoes)} · mortas pelo teste esperado: {len(mutacoes) - ruins}"
            )
            print(f"recusadas: 0 · sobreviventes ou mal atribuídas: {ruins}")
            print("\n".join(linhas))
            return 1 if ruins else 0
    finally:
        TRAVA.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
