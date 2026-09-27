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
    Mutacao(
        "cota: sem orçamento local, leva 403",
        "src/lifeos/gmail/service.py",
        "            if not self._gastos or usado + unidades <= ORCAMENTO_POR_MINUTO:",
        "            if True:",
        "tests/test_gmail_limpeza.py::test_caso_do_mac_raio_x_mais_limpeza_cabe_na_cota_sem_recusa",
    ),
    Mutacao(
        "cota: 403 de cota numa chamada não espera",
        "src/lifeos/gmail/service.py",
        "            if _eh_limite(exc) and espera is not None:",
        "            if False:",
        "tests/test_gmail_limpeza.py::test_arquivar_recusado_por_cota_tenta_de_novo",
    ),
    Mutacao(
        "cota: 403 de cota nos metadados não espera",
        "src/lifeos/gmail/service.py",
        "        if any(_eh_limite(e) for e in falhas.values()):",
        "        if False:",
        "tests/test_gmail_limpeza.py::test_recusa_por_cota_espera_cada_vez_mais_e_recupera",
    ),
    Mutacao(
        "cota: confirmação relê e-mail por e-mail",
        "src/lifeos/gmail/service.py",
        "        if permitidos is not None:\n            sai = [",
        "        if False:\n            sai = [",
        "tests/test_gmail_limpeza.py::test_confirmacao_nao_rele_email_por_email",
    ),
    Mutacao(
        "cota: o erro cru do Google (número do projeto) vai ao texto",
        "src/lifeos/gmail/service.py",
        "                raise LimiteDoGmail(_LIMITE) from exc",
        "                raise LimiteDoGmail(str(exc)) from exc",
        "tests/test_gmail_limpeza.py::test_cota_que_nunca_volta_vira_frase_sem_o_erro_cru",
    ),
    Mutacao(
        "aprovação: só o código, digitado sozinho, vai ao Gemini",
        "src/lifeos/assistant/agent.py",
        "        and confirmacao.aberta(limpeza.ACAO)",
        "        and False",
        "tests/test_gmail_aprovacao.py::test_so_o_numero_com_proposta_aberta_aprova_e_nao_vai_ao_gemini",
    ),
    Mutacao(
        "aprovação: número qualquer é roubado do Gemini sem proposta aberta",
        "src/lifeos/assistant/agent.py",
        "        and confirmacao.aberta(limpeza.ACAO)",
        "        and True",
        "tests/test_gmail_aprovacao.py::test_frase_comum_segue_para_o_gemini",
    ),
    Mutacao(
        "aprovação: a nota colada antes do sair (o bug do Mac)",
        "src/lifeos/assistant/agent.py",
        '        if prompt.lower() in ["sair", "exit", "quit"]:',
        "        if nota_pendente:\n"
        '            prompt, nota_pendente = f"{nota_pendente}\\n\\n{prompt}", ""\n'
        '        if prompt.lower() in ["sair", "exit", "quit"]:',
        "tests/test_gmail_aprovacao.py::test_a_sequencia_do_mac_nao_vaza_o_codigo_e_sair_sai",
    ),
    Mutacao(
        "aprovação: código vivo em frase livre vai ao Gemini",
        "src/lifeos/assistant/agent.py",
        "            if confirmacao.vivo(limpeza.ACAO, c, janela=limpeza.DESFAZER_POR)",
        "            if False",
        "tests/test_gmail_aprovacao.py::test_desfazer_em_frase_livre_age_sem_o_gemini",
    ),
    Mutacao(
        "aprovação: número que não é código vivo é roubado do Gemini",
        "src/lifeos/assistant/agent.py",
        "        if not vivos:\n            return None",
        '        if not vivos:\n            return _COMO_APROVAR, ""',
        "tests/test_gmail_aprovacao.py::test_numero_que_nao_e_codigo_vivo_segue_para_o_gemini",
    ),
    Mutacao(
        "confirmação: código feito fica vivo para sempre",
        "src/lifeos/confirmacao.py",
        '        return datetime.fromisoformat(linha["consumida_em"]) + janela >= agora',
        "        return True",
        "tests/test_confirmacao.py::test_vivo_so_enquanto_serve_para_algo",
    ),
    Mutacao(
        "pluggy: escrita fora da lista (PIX, apagar conexão) chega à rede",
        "src/lifeos/financas/pluggy.py",
        '    if metodo != "GET" and (metodo, caminho) not in _ESCRITAS_PERMITIDAS:',
        "    if False:",
        "tests/test_financas.py::test_escrita_fora_da_lista_e_recusada_antes_da_rede",
    ),
    Mutacao(
        "pluggy: a mensagem de erro ecoa o corpo (com o segredo)",
        "src/lifeos/financas/pluggy.py",
        'detalhe = json.loads(exc.read() or b"{}").get("codeDescription") or ""',
        'detalhe = json.loads(exc.read() or b"{}").get("message") or ""',
        "tests/test_financas.py::test_segredo_nunca_aparece_em_erro_nem_em_repr",
    ),
    Mutacao(
        "pluggy: ID estranho vira caminho da API",
        "src/lifeos/financas/pluggy.py",
        "    if not _UUID.fullmatch(limpo):",
        "    if False:",
        "tests/test_financas.py::test_id_estranho_nao_vira_caminho",
    ),
    Mutacao(
        "conectar: ID mandado sem o caminho secreto é aceito",
        "src/lifeos/financas/conectar.py",
        '            rota = self.path[len(base) :] if self.path.startswith(base + "/") else None',
        '            rota = "/" + self.path.rsplit("/", 1)[-1]',
        "tests/test_financas.py::test_id_mandado_por_outra_aba_sem_o_segredo_e_ignorado",
    ),
    Mutacao(
        # Sem escape nenhum: tirar só o do "<" é equivalente (o ">" escapado já impede o fechamento).
        "conectar: token com </script> fecha o script da página",
        "src/lifeos/financas/conectar.py",
        "    return json.dumps(valor).replace(",
        "    return json.dumps(valor) if True else json.dumps(valor).replace(",
        "tests/test_financas.py::test_token_malicioso_nao_fecha_o_script",
    ),
    Mutacao(
        "conectar: 'fechou' antes do ID perde a conexão criada",
        "src/lifeos/financas/conectar.py",
        "            resultado.tem_id.wait(tolerancia_s)",
        "            pass",
        "tests/test_financas.py::test_fechou_antes_do_id_chegar_ainda_pega_o_id",
    ),
    # Finanças (Sessão Pluggy): as três armadilhas medidas nas conexões do dono, o fuso, e o que
    # vem de terceiros na descrição de uma transação.
    Mutacao(
        "finanças: sentido pelo sinal (o do cartão vem positivo)",
        "src/lifeos/financas/service.py",
        '        saida = bruta.get("type") == "DEBIT"',
        "        saida = valor < 0",
        "tests/test_financas_dados.py::test_gasto_no_cartao_conta_mesmo_vindo_positivo",
    ),
    Mutacao(
        "finanças: fatura paga e movimento entre contas próprias viram gasto",
        "src/lifeos/financas/service.py",
        '            interna=interna(categoria, bruta.get("operationType"))\n'
        "            or paga_fatura(descricao, cartao=conta.cartao, saida=saida),",
        "            interna=False,",
        "tests/test_financas_dados.py::test_fatura_paga_nao_conta_em_dobro",
    ),
    Mutacao(
        "finanças: parcela futura entra no gasto do mês",
        "src/lifeos/financas/service.py",
        "    saidas = [t for t in externas if t.saida and t.dia <= hoje]",
        "    saidas = [t for t in externas if t.saida]",
        "tests/test_financas_dados.py::test_parcela_futura_fica_fora_do_total_e_e_contada",
    ),
    Mutacao(
        "finanças: estorno do cartão conta como renda",
        "src/lifeos/financas/service.py",
        "not t.saida and not t.cartao and t.dia <= hoje",
        "not t.saida and t.dia <= hoje",
        "tests/test_financas_dados.py::test_entrada_e_o_que_chegou_na_conta_sem_estorno_do_cartao",
    ),
    Mutacao(
        "finanças: dia da transação em UTC, não em Brasília",
        "src/lifeos/financas/service.py",
        "    return instante.astimezone(TIMEZONE).date() if instante else None",
        "    return instante.date() if instante else None",
        "tests/test_financas_dados.py::test_borda_do_mes_segue_o_fuso_e_nao_o_utc",
    ),
    Mutacao(
        "finanças: pede à Pluggy só o período exato e perde a borda do fuso",
        "src/lifeos/financas/service.py",
        "            (ate + timedelta(days=1)).isoformat(),",
        "            ate.isoformat(),",
        "tests/test_financas_dados.py::test_borda_do_mes_segue_o_fuso_e_nao_o_utc",
    ),
    Mutacao(
        "finanças: cursor ignorado, só a primeira página",
        "src/lifeos/financas/service.py",
        '                cursor = resposta.get("next")',
        "                cursor = None",
        "tests/test_financas_dados.py::test_segue_o_cursor_ate_o_fim",
    ),
    Mutacao(
        "finanças: transação ilegível some sem aviso",
        "src/lifeos/financas/service.py",
        "                        self.ignoradas += 1",
        "                        pass",
        "tests/test_financas_dados.py::test_transacao_sem_valor_ou_data_fica_fora_e_e_contada",
    ),
    Mutacao(
        "finanças: vencimento da fatura convertido de fuso (dia anterior)",
        "src/lifeos/financas/service.py",
        '        datadas = [(f, _data(f.get("dueDate"))) for f in faturas]',
        '        datadas = [(f, _dia(f.get("dueDate"))) for f in faturas]',
        "tests/test_financas_dados.py::test_ultima_fatura_fechada_e_a_de_vencimento_mais_recente",
    ),
    Mutacao(
        "finanças: compra que já tem fatura conta como sem fatura",
        "src/lifeos/financas/service.py",
        "    abertas = [t for t in externas if not t.fatura and t.dia <= hoje]",
        "    abertas = [t for t in externas if t.dia <= hoje]",
        "tests/test_financas_dados.py::test_fatura_sem_fatura_e_o_que_veio_depois_do_fechamento_sem_billid",
    ),
    Mutacao(
        "finanças: descrição fora do bloco de não confiável",
        "src/lifeos/financas/tools.py",
        '    return bloco(_DADOS_DO_BANCO, "\\n".join(_linha(t) for t in transacoes))',
        '    return "\\n".join(_linha(t) for t in transacoes)',
        "tests/test_financas_respostas.py::test_descricao_com_injecao_fica_dentro_do_bloco_neutralizada",
    ),
    Mutacao(
        "finanças: descrição sem redação (CPF vai ao Gemini)",
        "src/lifeos/financas/tools.py",
        '    return _redacao.redigir(_redacao.limpar_controles(texto or ""))',
        '    return _redacao.limpar_controles(texto or "")',
        "tests/test_financas_respostas.py::test_cpf_na_descricao_e_redigido",
    ),
    Mutacao(
        "finanças: conexão com erro de login não é avisada",
        "src/lifeos/financas/tools.py",
        "        if c.status not in _STATUS_OK:",
        "        if False:",
        "tests/test_financas_respostas.py::test_conexao_com_erro_de_login_e_avisada",
    ),
    Mutacao(
        "pluggy: escrita repetida depois de falha de conexão",
        "src/lifeos/financas/pluggy.py",
        '    esperas = ESPERAS_S if metodo == "GET" else ()',
        "    esperas = ESPERAS_S",
        "tests/test_financas.py::test_escrita_com_falha_de_conexao_nunca_repete",
    ),
    Mutacao(
        "pluggy: leitura desiste na primeira falha de conexão",
        "src/lifeos/financas/pluggy.py",
        '    esperas = ESPERAS_S if metodo == "GET" else ()',
        "    esperas = ()",
        "tests/test_financas.py::test_leitura_com_falha_de_conexao_e_tentada_de_novo",
    ),
    Mutacao(
        "finanças: pagamento de fatura do Nubank (sem categoria certa) vira gasto",
        "src/lifeos/financas/service.py",
        '    return saida and texto == "pagamento de fatura"',
        "    return False",
        "tests/test_financas_dados.py::test_pagamento_de_fatura_do_nubank_pela_descricao_nao_e_gasto",
    ),
    Mutacao(
        "finanças: qualquer 'pagamento de fatura ...' na conta some do gasto",
        "src/lifeos/financas/service.py",
        '    return saida and texto == "pagamento de fatura"',
        '    return saida and texto.startswith("pagamento de fatura")',
        "tests/test_financas_dados.py::test_conta_paga_como_pagamento_de_fatura_de_outra_coisa_e_gasto",
    ),
    Mutacao(
        "finanças: pagamento chegando no cartão sem fatura vira estorno",
        "src/lifeos/financas/service.py",
        '        return not saida and texto.startswith("pagamento")',
        "        return False",
        "tests/test_financas_dados.py::test_pagamento_no_cartao_sem_categoria_nao_desconta_da_fatura",
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
