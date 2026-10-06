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
        "liberar: aprovado com o navegador ocupado diz que não achou o botão",
        "src/lifeos/browser/liberacao.py",
        '    if resultado.status == "error" and not resultado.steps:',
        "    if False:",
        "tests/test_browser_liberacao.py::test_o_texto_diz_o_que_aconteceu_com_o_clique",
    ),
    Mutacao(
        "trava: pasta que não abre vira exceção em vez de recusa",
        "src/lifeos/browser/trava.py",
        '        raise Indisponivel(f"não consegui abrir {caminho}: {exc}") from exc',
        "        raise",
        "tests/test_browser_trava.py::test_sem_poder_abrir_a_trava_nao_navega",
    ),
    Mutacao(
        "trava: só dentro do processo (sem flock)",
        "src/lifeos/browser/trava.py",
        "                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n",
        "                pass\n",
        "tests/test_browser_trava.py::test_outro_processo_segurando_recusa_na_hora_dizendo_quem",
    ),
    Mutacao(
        "trava: espera o outro em vez de recusar na hora",
        "src/lifeos/browser/trava.py",
        "fcntl.LOCK_EX | fcntl.LOCK_NB",
        "fcntl.LOCK_EX",
        "tests/test_browser_trava.py::test_outro_processo_segurando_recusa_na_hora_dizendo_quem",
    ),
    Mutacao(
        "trava: o runner ignora quem está usando",
        "src/lifeos/browser/jev_runner.py",
        '                if ocupado is not None:\n                    return _erro("busy"',
        '                if False:\n                    return _erro("busy"',
        "tests/test_browser_trava.py::test_outro_processo_segurando_recusa_na_hora_dizendo_quem",
    ),
    Mutacao(
        "trava: o --doctor roda com tarefa em curso",
        "src/lifeos/cli.py",
        "            if ocupado is not None:\n                descricao = limpar_controles(",
        "            if False:\n                descricao = limpar_controles(",
        "tests/test_browser_trava.py::test_doctor_com_tarefa_em_curso_nao_roda",
    ),
    Mutacao(
        "trava: objetivo gravado sem redação",
        "src/lifeos/browser/trava.py",
        '    limpo = _redacao.limpar_controles(_redacao.redigir(str(texto or ""))) or ""',
        '    limpo = _redacao.limpar_controles(str(texto or "")) or ""',
        "tests/test_browser_trava.py::test_objetivo_no_arquivo_vai_redigido_limpo_e_curto",
    ),
    Mutacao(
        "trava: 'ocupado' sem dizer quem ao Gemini",
        "src/lifeos/browser/mensagens.py",
        '    "busy",\n    "trava_indisponivel",\n}',
        '    "trava_indisponivel",\n}',
        "tests/test_browser_trava.py::test_o_gemini_recebe_quem_usa_neutralizado",
    ),
    Mutacao(
        "protocolo: nonce não conferido",
        "src/lifeos/browser/jev_runner.py",
        '    if not isinstance(evento, dict) or evento.get("nonce") != nonce:',
        "    if not isinstance(evento, dict):",
        "tests/test_browser_jev_runner.py::test_terminal_forjado_sem_nonce_nao_vira_resultado",
    ),
    Mutacao(
        "protocolo: schema não conferido",
        "src/lifeos/browser/jev_runner.py",
        '    if type(schema) is not int or schema != SCHEMA or evento.get("type") not in TIPOS:',
        '    if evento.get("type") not in TIPOS:',
        "tests/test_browser_jev_runner.py::test_parse_event_recusa_o_que_nao_e_desta_execucao",
    ),
    Mutacao(
        "protocolo: nonce fixo entre execuções",
        "src/lifeos/browser/jev_runner.py",
        "secrets.token_hex(8)",
        '"0" * 16',
        "tests/test_browser_jev_runner.py::test_o_filho_recebe_um_nonce_novo_a_cada_execucao",
    ),
    Mutacao(
        "loop: estado sem ação nova entra na conta do ciclo",
        "src/lifeos/browser/_jev_subprocess.py",
        "            nova_acao = _passos(state) > passos_vistos",
        "            nova_acao = True",
        "tests/test_jev_subprocess_main.py::test_estado_sem_acao_nova_nao_desmancha_o_ciclo",
    ),
    Mutacao(
        "loop: voltar ao mesmo vídeo não conta (o rastro do YouTube)",
        "src/lifeos/browser/_jev_subprocess.py",
        "_oscilando(assinaturas) or _oscilando(amplas) or _revisitando(decididas)",
        "_oscilando(assinaturas) or _oscilando(amplas)",
        "tests/test_jev_subprocess_main.py::test_rastro_do_youtube_para_na_segunda_volta_ao_mesmo_video",
    ),
    Mutacao(
        "loop: 'Mostrar mais' seguido vira volta",
        "src/lifeos/browser/_jev_subprocess.py",
        "        if assinatura != anterior:",
        "        if True:",
        "tests/test_jev_subprocess_main.py::test_mostrar_mais_seguido_nao_e_loop",
    ),
    Mutacao(
        "fuso: o chat nunca avisa que o Viking e a agenda discordam",
        "src/lifeos/calendar/tools.py",
        "    if do_viking == da_agenda:",
        "    if True:",
        "tests/test_calendar_fuso_da_agenda.py::test_fuso_adivinhado_pela_maquina_e_agenda_noutro_avisa",
    ),
    Mutacao(
        "fuso: renovação recusada escapa da conferência (derrubaria o chat)",
        "src/lifeos/google_auth.py",
        "        except Exception:  # noqa: BLE001 - renovação recusada (ou sem rede): sem aviso, sem login",
        "        except ValueError:",
        "tests/test_calendar_fuso_da_agenda.py::test_renovacao_recusada_nao_abre_login",
    ),
    Mutacao(
        "fuso: a conferência não renova o token (o aviso ficava mudo no Mac)",
        "src/lifeos/google_auth.py",
        "    if not creds.valid and creds.expired and creds.refresh_token:",
        "    if False:",
        "tests/test_calendar_fuso_da_agenda.py::test_token_vencido_renova_em_silencio",
    ),
    Mutacao(
        "fuso: avisa mesmo com o fuso escolhido no .env",
        "src/lifeos/calendar/tools.py",
        '    if TIMEZONE_ESCOLHIDO:\n        return ""',
        '    if False:\n        return ""',
        "tests/test_calendar_fuso_da_agenda.py::test_fuso_escolhido_no_env_nao_avisa_mesmo_com_a_agenda_noutro",
    ),
    Mutacao(
        "fuso: a abertura do chat não confere",
        "src/lifeos/assistant/agent.py",
        "    fuso = aviso_de_fuso()",
        '    fuso = ""',
        "tests/test_calendar_fuso_da_agenda.py::test_o_chat_mostra_o_aviso_ao_abrir",
    ),
    Mutacao(
        "versão: no pipe o bloco sai depois do harness",
        "src/lifeos/cli.py",
        "            print(versao_jev.texto(versao_jev.conferir()), flush=True)",
        "            print(versao_jev.texto(versao_jev.conferir()))",
        "tests/test_browser_versao_jev.py::test_a_versao_sai_antes_do_harness_mesmo_num_pipe",
    ),
    Mutacao(
        "ambiente: a chave do Gemini passa para o Jev",
        "src/lifeos/browser/jev_runner.py",
        'AMBIENTE_PREFIXOS = ("LC_", "XDG_", "UV_", "BH_", "BU_", "BROWSER_HARNESS_")',
        'AMBIENTE_PREFIXOS = ("GEMINI_", "LC_", "XDG_", "UV_", "BH_", "BU_", "BROWSER_HARNESS_")',
        "tests/test_browser_ambiente.py::test_so_a_lista_passa_e_com_o_valor_igual",
    ),
    Mutacao(
        "ambiente: prefixo sem o '_' (BU pega BUDGET_SECRET)",
        "src/lifeos/browser/jev_runner.py",
        'AMBIENTE_PREFIXOS = ("LC_", "XDG_", "UV_", "BH_", "BU_", "BROWSER_HARNESS_")',
        'AMBIENTE_PREFIXOS = ("LC_", "XDG_", "UV_", "BH_", "BU", "BROWSER_HARNESS_")',
        "tests/test_browser_ambiente.py::test_so_a_lista_passa_e_com_o_valor_igual",
    ),
    Mutacao(
        "ambiente: um UV_ENV_FILE herdado escolhe o .env do Jev",
        "src/lifeos/browser/jev_runner.py",
        "        if nome not in AMBIENTE_EXCETO\n        and (",
        "        if True\n        and (",
        "tests/test_browser_ambiente.py::test_so_a_lista_passa_e_com_o_valor_igual",
    ),
    Mutacao(
        "ambiente: o Jev herda todo o ambiente do Viking",
        "src/lifeos/browser/jev_runner.py",
        "            env=ambiente_do_jev(nonce),",
        '            env={**os.environ, "VIKING_JEV_NONCE": nonce},',
        "tests/test_browser_ambiente.py::test_o_jev_recebe_so_a_lista_de_ponta_a_ponta",
    ),
    Mutacao(
        "ambiente: o --doctor herda todo o ambiente do Viking",
        "src/lifeos/cli.py",
        "                return subprocess.call(cmd, env=jev_runner.ambiente_do_jev())",
        "                return subprocess.call(cmd)",
        "tests/test_browser_ambiente.py::test_o_doctor_recebe_so_a_lista_de_ponta_a_ponta",
    ),
    Mutacao(
        "ambiente: o --doctor sem o .env do Jev",
        "src/lifeos/browser/jev_runner.py",
        '    return [*_uv_run(None, None, None), "browser-harness", "doctor"]',
        '    return [UV_BIN, "run", "--directory", str(JEV_DIR), "browser-harness", "doctor"]',
        "tests/test_browser_ambiente.py::test_o_doctor_usa_o_env_do_jev_como_a_tarefa",
    ),
    Mutacao(
        "versão: o patch dá sempre presente",
        "src/lifeos/browser/versao_jev.py",
        '        return MARCA_DO_PATCH in (pasta / ARQUIVO_DO_PATCH).read_text(encoding="utf-8")',
        '        (pasta / ARQUIVO_DO_PATCH).read_text(encoding="utf-8")\n        return True',
        "tests/test_browser_versao_jev.py::test_sem_o_patch_avisa",
    ),
    Mutacao(
        "versão: clone sem .git responde com o ramo do Viking",
        "src/lifeos/browser/versao_jev.py",
        "        if raiz.resolve() != pasta.resolve():",
        "        if False:",
        "tests/test_browser_versao_jev.py::test_clone_sem_git_dentro_de_outro_repo_nao_herda_o_ramo_de_fora",
    ),
    Mutacao(
        "versão: o chat não avisa",
        "src/lifeos/browser/__init__.py",
        "    if not silencioso:\n        versao_jev.avisar()",
        "    if False:\n        versao_jev.avisar()",
        "tests/test_browser_versao_jev.py::test_o_aviso_vai_para_o_dono_e_nao_para_o_gemini",
    ),
    Mutacao(
        "versão: `viking browser` não avisa",
        "src/lifeos/cli.py",
        "    versao_jev.avisar()\n    resultado: BrowserResult = run_jev(",
        "    resultado: BrowserResult = run_jev(",
        "tests/test_browser_versao_jev.py::test_viking_browser_json_avisa_so_no_stderr",
    ),
    Mutacao(
        "fuso: a tool do Gemini aceita o fuso inventado",
        "src/lifeos/calendar/service.py",
        "    return _offset(dt), _offset(do_dono)",
        "    return None",
        "tests/test_calendar_tools.py::test_criar_evento_recusa_fuso_diferente_do_dono",
    ),
    Mutacao(
        "fuso: o do dono de hoje, não o da data do evento",
        "src/lifeos/calendar/service.py",
        "    do_dono = dt.replace(tzinfo=TIMEZONE)",
        "    do_dono = datetime.now(TIMEZONE)",
        "tests/test_calendar_tools.py::test_fuso_do_dono_segue_o_horario_de_verao",
    ),
    Mutacao(
        "fuso: só o início é conferido",
        "src/lifeos/calendar/tools.py",
        '    recusa = recusa_de_fuso("NÃO criei o evento", start_time, end_time)',
        '    recusa = recusa_de_fuso("NÃO criei o evento", start_time)',
        "tests/test_calendar_tools.py::test_fuso_so_no_fim_tambem_e_recusado",
    ),
    Mutacao(
        "fuso: reagendar sem a régua",
        "src/lifeos/calendar/tools.py",
        '    recusa = recusa_de_fuso("NÃO reagendei", novo_inicio, novo_fim)',
        '    recusa = ""',
        "tests/test_calendar_tools.py::test_reagendar_recusa_fuso_diferente_do_dono",
    ),
    Mutacao(
        "fuso: lembrete sem a régua",
        "src/lifeos/assistant/agent.py",
        '    recusa = recusa_de_fuso("NÃO criei o lembrete", quando)',
        '    recusa = ""',
        "tests/test_assistant_tools.py::test_lembrete_com_fuso_diferente_do_dono_e_recusado",
    ),
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
    # O furo de 2026-09-28 (Sessão 8): cada peça do canonizador de host tem o seu disfarce.
    Mutacao(
        "bloqueio: view-source/blob/filesystem não são desembrulhados",
        "src/lifeos/browser/_redacao.py",
        "if not achado or achado.group(1).lower() not in _EMBRULHOS:",
        "if True:",
        "tests/test_redacao.py::test_dominio_disfarcado_bloqueado",
    ),
    Mutacao(
        "envelope: página em view-source do banco sai para o OpenRouter",
        "src/lifeos/browser/_redacao.py",
        "if not achado or achado.group(1).lower() not in _EMBRULHOS:",
        "if True:",
        "tests/test_jev_subprocess_main.py::test_pagina_embrulhando_o_banco_nao_sai_nada",
    ),
    Mutacao(
        "bloqueio: embrulho sem teto passa",
        "src/lifeos/browser/_redacao.py",
        "        url = url[achado.end() :].strip(_C0_OU_ESPACO)\n    return None",
        "        url = url[achado.end() :].strip(_C0_OU_ESPACO)\n    return url",
        "tests/test_redacao.py::test_desembrulho_tem_fim",
    ),
    Mutacao(
        "bloqueio: https:banco e barra invertida passam",
        "src/lifeos/browser/_redacao.py",
        "    if achado and achado.group(1).lower() in _ESPECIAIS:",
        "    if False:",
        "tests/test_redacao.py::test_dominio_disfarcado_bloqueado",
    ),
    Mutacao(
        "bloqueio: %69tau passa",
        "src/lifeos/browser/_redacao.py",
        'unicodedata.normalize("NFKC", unquote(host, errors="replace"))',
        'unicodedata.normalize("NFKC", host)',
        "tests/test_redacao.py::test_dominio_disfarcado_bloqueado",
    ),
    Mutacao(
        "bloqueio: letras de largura dupla passam",
        "src/lifeos/browser/_redacao.py",
        'unicodedata.normalize("NFKC", unquote(host, errors="replace"))',
        'unquote(host, errors="replace")',
        "tests/test_redacao.py::test_dominio_disfarcado_bloqueado",
    ),
    Mutacao(
        "bloqueio: hífen invisível passa",
        "src/lifeos/browser/_redacao.py",
        'if c != chr(0x34F) and unicodedata.category(c) != "Cf"',
        "if True",
        "tests/test_redacao.py::test_dominio_disfarcado_bloqueado",
    ),
    Mutacao(
        "bloqueio: file:/view-source: abrem o subprocesso",
        "src/lifeos/browser/jev_runner.py",
        "    if not _redacao.esquema_permitido(url):",
        "    if False:",
        "tests/test_browser_seguranca.py::test_esquema_recusado_nao_abre_subprocesso",
    ),
    Mutacao(
        "bloqueio: qualquer esquema serve de endereço inicial",
        "src/lifeos/browser/_redacao.py",
        '    if esquema not in {"http", "https", "data"}:\n        return False',
        '    if esquema not in {"http", "https", "data"}:\n        return True',
        "tests/test_redacao.py::test_esquema_do_endereco_inicial_recusado",
    ),
    # Enviar e-mail (Sessão 8, D46): cada trava do envio, com o teste que a prende.
    Mutacao(
        "envio: parecido com o dono sai sem código",
        "src/lifeos/gmail/envio.py",
        "    if set(rascunho.para) == {dono}:",
        "    if dono in set(rascunho.para):",
        "tests/test_gmail_envio.py::test_parecido_com_o_dono_ou_junto_com_outro_pede_codigo",
    ),
    Mutacao(
        "envio: sem limite para a própria conta",
        "src/lifeos/gmail/envio.py",
        "        if usados >= LIMITE_LIVRE:",
        "        if False:",
        "tests/test_gmail_envio.py::test_o_21o_para_a_conta_em_24h_e_recusado",
    ),
    Mutacao(
        "envio: 'eu' não vira a própria conta (o Gemini volta a perguntar o endereço)",
        "src/lifeos/gmail/envio.py",
        "dono if str(bruto).strip().lower() in _EU else service.endereco_valido(bruto)",
        "service.endereco_valido(bruto)",
        "tests/test_gmail_envio.py::test_eu_e_a_propria_conta_e_sai_sem_codigo",
    ),
    Mutacao(
        "envio: proposta sem terminal",
        "src/lifeos/gmail/envio.py",
        "    if not _terminal():",
        "    if False:",
        "tests/test_gmail_envio.py::test_sem_terminal_nao_ha_proposta",
    ),
    Mutacao(
        "envio: caractere invisível passa para o texto aprovado",
        "src/lifeos/gmail/envio.py",
        "    if ruim is not None:",
        "    if False:",
        "tests/test_gmail_envio.py::test_texto_com_invisivel_ou_controle_e_recusado",
    ),
    Mutacao(
        "envio: send fora do registro de ações",
        "src/lifeos/gmail/service.py",
        '    with registro.acao("gmail.enviar", parametros) as marca:',
        "    for marca in [registro.Marca(0)]:",
        "tests/test_registro_ganchos.py::test_todo_efeito_externo_passa_pelo_registro",
    ),
    Mutacao(
        "envio: 5xx depois de enviar vira 'falhou' (o dono manda de novo)",
        "src/lifeos/gmail/service.py",
        "            raise FalhaDaApi(_descrever(exc), incerta=not certa) from exc",
        "            raise FalhaDaApi(_descrever(exc)) from exc",
        "tests/test_gmail_envio.py::test_5xx_no_envio_e_incerta_e_o_codigo_foi_gasto",
    ),
    Mutacao(
        "envio: o código vai no retorno da tool",
        "src/lifeos/gmail/tools.py",
        '    return f"Proposta pronta: e-mail para {para}',
        '    return f"Proposta pronta ({pedido.codigo}): e-mail para {para}',
        "tests/test_gmail_envio_chat.py::test_para_outra_pessoa_o_texto_e_o_codigo_vao_so_ao_terminal",
    ),
    Mutacao(
        "envio: o código do e-mail cai na limpeza",
        "src/lifeos/assistant/agent.py",
        "    if tipo is not None and tipo.acao == aprovacoes.GMAIL_ENVIAR:",
        "    if False:",
        "tests/test_gmail_envio_chat.py::test_confirma_envia_e_nao_arquiva",
    ),
    Mutacao(
        "envelope: página sai sem redação para o OpenRouter",
        "src/lifeos/browser/_jev_subprocess.py",
        "decisao = choose(_redigida(page), goal, history)",
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
        "liberar: dinheiro no contêiner passa quando a categoria recusada é outra",
        "src/lifeos/browser/_acoes_sensiveis.py",
        '        and "dinheiro" not in sinais(acao, guard)\n',
        "",
        "tests/test_jev_subprocess_main.py::test_dinheiro_no_conteiner_nunca_e_liberado",
    ),
    Mutacao(
        "liberar: a mesma liberação passa dois cliques",
        "src/lifeos/browser/_jev_subprocess.py",
        "        liberacao = pendente.pop() if pendente else None",
        "        liberacao = pendente[0] if pendente else None",
        "tests/test_jev_subprocess_main.py::test_liberacao_deixa_passar_so_o_primeiro_clique",
    ),
    Mutacao(
        "liberar: libera sem conferir a digital",
        "src/lifeos/browser/_jev_subprocess.py",
        "        if liberavel and liberacao == digital:",
        "        if liberavel and liberacao is not None:",
        "tests/test_jev_subprocess_main.py::test_outro_site_ou_outro_botao_nao_e_liberado",
    ),
    Mutacao(
        "liberar: categoria dinheiro aceita no argumento",
        "src/lifeos/browser/_acoes_sensiveis.py",
        '    if dados["categoria"] not in LIBERAVEIS:',
        "    if False:",
        "tests/test_jev_subprocess_main.py::test_liberacao_invalida_recusa_antes_de_navegar",
    ),
    Mutacao(
        "liberar: rótulo com dinheiro aceito no argumento",
        "src/lifeos/browser/_acoes_sensiveis.py",
        '    if "dinheiro" in sinais({"kind": "click", "label": rotulo}):',
        "    if False:",
        "tests/test_jev_subprocess_main.py::test_liberacao_invalida_recusa_antes_de_navegar",
    ),
    Mutacao(
        "liberar: liberação de outro site que não o de --url",
        "src/lifeos/browser/_jev_subprocess.py",
        '    if _acoes_sensiveis.esquema_host(url) != liberar["esquema_host"]:',
        "    if False:",
        "tests/test_jev_subprocess_main.py::test_liberacao_invalida_recusa_antes_de_navegar",
    ),
    Mutacao(
        "liberar: opção abreviada vira --liberar-uma",
        "src/lifeos/browser/_jev_subprocess.py",
        "allow_abbrev=False",
        "allow_abbrev=True",
        "tests/test_jev_subprocess_main.py::test_opcao_abreviada_nao_vira_liberacao",
    ),
    Mutacao(
        "liberar: dinheiro só no contêiner, não no rótulo nem no link",
        "src/lifeos/browser/_acoes_sensiveis.py",
        "    textos = [*candidatos, normalizar(href), escopo]",
        "    textos = [escopo]",
        "tests/test_acoes_sensiveis.py::test_sair_e_pagar_tem_os_dois_sinais",
    ),
    Mutacao(
        "liberar: porta fora da digital do site",
        "src/lifeos/browser/_acoes_sensiveis.py",
        ' + (f":{porta}" if porta is not None else "")',
        "",
        "tests/test_jev_subprocess_main.py::test_outro_site_ou_outro_botao_nao_e_liberado",
    ),
    Mutacao(
        "liberar: recusa sem a digital no evento de erro",
        "src/lifeos/browser/_jev_subprocess.py",
        '                {"acao_sensivel": exc.digital, "liberavel": exc.liberavel}',
        "                {}",
        "tests/test_jev_subprocess_main.py::test_recusa_traz_a_digital_e_a_url",
    ),
    Mutacao(
        "liberar: proposta (e código na tela) sem terminal interativo",
        "src/lifeos/browser/__init__.py",
        "    proposta = liberacao.propor(resultado) if liberacao.terminal_interativo() else None",
        "    proposta = liberacao.propor(resultado)",
        "tests/test_browser_liberacao.py::test_sem_terminal_nao_ha_proposta",
    ),
    Mutacao(
        "liberar: o código vai no texto que o Gemini lê",
        "src/lifeos/browser/__init__.py",
        '        texto = f"{texto}\\n{liberacao.AVISO_AO_GEMINI}"',
        '        texto = f"{texto}\\n{liberacao.AVISO_AO_GEMINI} {proposta.codigo}"',
        "tests/test_browser_liberacao.py::test_recusa_liberavel_vira_proposta_e_o_codigo_so_vai_ao_terminal",
    ),
    Mutacao(
        "liberar: o pai propõe digital de dinheiro ou fora da forma",
        "src/lifeos/browser/liberacao.py",
        "        _acoes_sensiveis.ler_liberacao(json.dumps(digital))\n",
        "        pass\n",
        "tests/test_browser_liberacao.py::test_o_que_nao_se_libera_nao_vira_proposta",
    ),
    Mutacao(
        "liberar: o pai propõe para um site diferente do da página",
        "src/lifeos/browser/liberacao.py",
        '    if _acoes_sensiveis.esquema_host(bruto["url"]) != digital["esquema_host"]:',
        "    if False:",
        "tests/test_browser_liberacao.py::test_o_que_nao_se_libera_nao_vira_proposta",
    ),
    Mutacao(
        "liberar: reexecução sem o teto curto de ações",
        "src/lifeos/browser/liberacao.py",
        "        max_acoes=MAX_ACOES,\n",
        "",
        "tests/test_browser_liberacao.py::test_aprovar_faz_so_aquele_clique_com_o_objetivo_do_viking",
    ),
    Mutacao(
        "liberar: o código aprova sem ser gasto",
        "src/lifeos/browser/liberacao.py",
        "    aprovado = confirmacao.consumir(ACAO, codigo)",
        "    aprovado = confirmacao.abertas(ACAO)[0]",
        "tests/test_browser_liberacao.py::test_o_codigo_serve_uma_vez",
    ),
    Mutacao(
        "chat: código do clique cai no despacho da limpeza",
        "src/lifeos/assistant/agent.py",
        "    if tipo is not None and tipo.acao == aprovacoes.NAVEGADOR_CLIQUE:",
        "    if False:",
        "tests/test_browser_liberacao.py::test_chat_confirma_libera_e_o_gemini_nunca_ve_o_codigo",
    ),
    Mutacao(
        "chat: o clique só se aprova no terminal",
        "src/lifeos/aprovacoes.py",
        "    Tipo(NAVEGADOR_CLIQUE, janela=timedelta(0), no_chat=True),",
        "    Tipo(NAVEGADOR_CLIQUE, janela=timedelta(0), no_chat=False),",
        "tests/test_browser_liberacao.py::test_chat_confirma_libera_e_o_gemini_nunca_ve_o_codigo",
    ),
    Mutacao(
        "liberar: `viking browser --json` propõe",
        "src/lifeos/cli.py",
        "        print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))\n        return _saida_do_navegador(resultado)\n",
        "        print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))\n",
        "tests/test_browser_liberacao.py::test_cli_json_nao_propoe",
    ),
    Mutacao(
        "liberar: a URL da recusa chega sem redação",
        "src/lifeos/browser/jev_runner.py",
        '            {**resultado.acao_sensivel, "url": _url_limpa(resultado.acao_sensivel["url"])}',
        "            {**resultado.acao_sensivel}",
        "tests/test_browser_jev_runner.py::test_a_recusa_traz_a_digital_com_a_url_redigida",
    ),
    Mutacao(
        "liberar: objetivo separado do `--goal` (vira opção)",
        "src/lifeos/browser/jev_runner.py",
        '    cmd += [f"--goal={goal}" for goal in goals]',
        '    cmd += [a for goal in goals for a in ("--goal", goal)]',
        "tests/test_browser_jev_runner.py::test_objetivo_e_url_que_parecem_opcao_nao_viram_liberacao",
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
        "        except RefreshError:\n            # Revogado ou vencido de vez",
        "        except ZeroDivisionError:\n            # Revogado ou vencido de vez",
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
        "    if linha.expira_em < agora:",
        "    if False:",
        "tests/test_confirmacao.py::test_codigo_vencido_nao_aprova",
    ),
    Mutacao(
        "confirmação: proposta nova não invalida a velha",
        "src/lifeos/confirmacao_sqlite.py",
        "        if substituir:\n            conn.execute(",
        "        if False:\n            conn.execute(",
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
        "        and any(confirmacao.aberta(t.acao) for t in aprovacoes.do_chat())",
        "        and False",
        "tests/test_gmail_aprovacao.py::test_so_o_numero_com_proposta_aberta_aprova_e_nao_vai_ao_gemini",
    ),
    Mutacao(
        "aprovação: número qualquer é roubado do Gemini sem proposta aberta",
        "src/lifeos/assistant/agent.py",
        "        and any(confirmacao.aberta(t.acao) for t in aprovacoes.do_chat())",
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
        "        if confirmacao.vivo(tipo.acao, c, janela=tipo.janela)",
        "        if False",
        "tests/test_gmail_aprovacao.py::test_desfazer_em_frase_livre_age_sem_o_gemini",
    ),
    Mutacao(
        "aprovação: número que não é código vivo é roubado do Gemini",
        "src/lifeos/assistant/agent.py",
        '                return NAO_E_CODIGO_AQUI, ""\n            return None',
        '                return NAO_E_CODIGO_AQUI, ""\n            return _COMO_APROVAR, ""',
        "tests/test_gmail_aprovacao.py::test_numero_que_nao_e_codigo_vivo_segue_para_o_gemini",
    ),
    Mutacao(
        "confirmação: código feito fica vivo para sempre",
        "src/lifeos/confirmacao.py",
        "        return linha.consumida_em + janela >= agora",
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
        '            interna=interna(categoria, bruta.get("operationType"), categoria_id)\n'
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
        "    return instante.astimezone(FUSO_DOS_BANCOS).date() if instante else None",
        "    return instante.date() if instante else None",
        "tests/test_financas_dados.py::test_borda_do_mes_segue_o_fuso_e_nao_o_utc",
    ),
    Mutacao(
        "finanças: dia da transação no fuso do dono, não no do banco",
        "src/lifeos/financas/service.py",
        "    return instante.astimezone(FUSO_DOS_BANCOS).date() if instante else None",
        "    return instante.astimezone(TIMEZONE).date() if instante else None",
        "tests/test_financas_dados.py::test_dia_da_transacao_e_o_do_banco_onde_quer_que_o_dono_esteja",
    ),
    Mutacao(
        "agenda: horário repassado no fuso da agenda, não no do dono",
        "src/lifeos/calendar/service.py",
        '        inicio=no_fuso_do_dono(inicio.get("dateTime")) or inicio.get("date") or "sem data",',
        '        inicio=inicio.get("dateTime") or inicio.get("date") or "sem data",',
        "tests/test_calendar_fuso_da_agenda.py::test_horario_da_agenda_chega_no_fuso_do_dono",
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
    Mutacao(
        "finanças: PIX para outra pessoa misturado às compras",
        "src/lifeos/financas/service.py",
        "            transferencia=categoria_id in _TRANSFERENCIA_A_OUTROS,",
        "            transferencia=False,",
        "tests/test_financas_dados.py::test_pix_para_outra_pessoa_e_gasto_em_linha_propria",
    ),
    Mutacao(
        "finanças: 'mesma titularidade - PIX' vira gasto",
        "src/lifeos/financas/service.py",
        "        or categoria_id.startswith(_PREFIXO_MESMA_TITULARIDADE)",
        "        or False",
        "tests/test_financas_dados.py::test_mesma_titularidade_por_pix_e_interna",
    ),
    # Sessão 5: vários tipos de aprovação.
    Mutacao(
        "confirmação: o mesmo código em duas ações",
        "src/lifeos/confirmacao_sqlite.py",
        "        while (codigo := sortear()) in reservados:",
        "        while (codigo := sortear()) in ():",
        "tests/test_confirmacao.py::test_codigo_nao_se_repete_entre_acoes",
    ),
    Mutacao(
        "confirmação: proposta substituída libera o número na hora",
        "src/lifeos/confirmacao_sqlite.py",
        '"WHERE expira_em >= ? OR (estado = ? AND consumida_em >= ?)",',
        "\"WHERE (estado = 'aberta' AND expira_em >= ?) OR (estado = ? AND consumida_em >= ?)\",",
        "tests/test_confirmacao.py::test_codigo_substituido_nao_volta_enquanto_nao_vence",
    ),
    Mutacao(
        "confirmação: validade da proposta ignorada",
        "src/lifeos/confirmacao.py",
        "        expira_em=agora + validade,",
        "        expira_em=agora + VALIDADE,",
        "tests/test_confirmacao.py::test_validade_da_proposta_pode_ser_maior",
    ),
    Mutacao(
        "aprovação: código de pedido do MCP aprovado pelo chat",
        "src/lifeos/assistant/agent.py",
        '    if tipo is not None and not tipo.no_chat:\n        return _SO_NO_TERMINAL, ""',
        '    if False:\n        return _SO_NO_TERMINAL, ""',
        "tests/test_aprovacoes.py::test_codigo_do_mcp_no_chat_aponta_o_terminal_e_nao_age",
    ),
    Mutacao(
        "aprovação: uma nota ao Gemini apaga a outra",
        "src/lifeos/assistant/turno.py",
        '    return "\\n".join(n for n in (pendente, nova) if n)',
        "    return nova or pendente",
        "tests/test_aprovacoes.py::test_notas_ao_gemini_se_somam",
    ),
    # Sessão 5: registro de ações, desfazer e pedidos pelo MCP.
    Mutacao(
        "mcp: apagar pelo MCP apaga direto, sem aprovação",
        "src/lifeos/mcp_server/server.py",
        "    return _resultado(calendario.responder_pedir_apagar(event_id, titulo_esperado))",
        "    return _resultado(calendario.responder_apagar(event_id, titulo_esperado))",
        "tests/test_mcp_aprovacao.py::test_apagar_pelo_mcp_so_pede_e_o_codigo_nao_sai",
    ),
    Mutacao(
        "aprovar: roda sem terminal interativo (um agente lê o código)",
        "src/lifeos/cli.py",
        "    if not (sys.stdin.isatty() and sys.stdout.isatty()):",
        "    if False:",
        "tests/test_mcp_aprovacao.py::test_aprovar_sem_terminal_interativo_recusa",
    ),
    Mutacao(
        "aprovar: evento que mudou desde o pedido é mexido",
        "src/lifeos/calendar/service.py",
        "    if mudou:",
        "    if False:",
        "tests/test_mcp_aprovacao.py::test_evento_que_mudou_desde_o_pedido_nao_e_mexido",
    ),
    Mutacao(
        "pedidos: sem limite de pedidos abertos",
        "src/lifeos/calendar/service.py",
        "    if abertos >= MAX_PEDIDOS_ABERTOS or na_hora >= MAX_PEDIDOS_POR_HORA:",
        "    if False:",
        "tests/test_mcp_aprovacao.py::test_limite_de_pedidos_abertos",
    ),
    Mutacao(
        "pedidos: um pedido do MCP some quando chega outro",
        "src/lifeos/calendar/service.py",
        "substituir=False",
        "substituir=True",
        "tests/test_mcp_aprovacao.py::test_dois_pedidos_convivem",
    ),
    Mutacao(
        "registro: guarda texto sem redação",
        "src/lifeos/registro.py",
        "        return _redacao.redigir(_redacao.limpar_controles(valor))[:MAX_TEXTO]",
        "        return valor",
        "tests/test_registro.py::test_dado_sensivel_e_controle_saem_redigidos",
    ),
    Mutacao(
        "registro: purga antes dos 30 dias",
        "src/lifeos/registro.py",
        "RETENCAO = timedelta(days=30)",
        "RETENCAO = timedelta(days=28)",
        "tests/test_registro.py::test_purga_depois_de_30_dias",
    ),
    Mutacao(
        "registro: falha ambígua vira 'falhou' (e o dono repete)",
        "src/lifeos/registro.py",
        "        estado = INCERTA if _eh_incerta(exc) else FALHOU",
        "        estado = FALHOU",
        "tests/test_registro.py::test_falha_ambigua_e_incerta",
    ),
    Mutacao(
        "calendário: 5xx ou tempo esgotado tratados como falha certa",
        "src/lifeos/calendar/service.py",
        "        raise FalhaDaApi(str(exc), incerta=not (status and 400 <= status < 500)) from exc",
        "        raise FalhaDaApi(str(exc), incerta=False) from exc",
        "tests/test_registro_ganchos.py::test_falha_depois_de_enviar_e_incerta",
    ),
    Mutacao(
        "calendário: resposta ambígua diz 'NÃO apaguei'",
        "src/lifeos/calendar/tools.py",
        "        if exc.incerta:\n"
        "            return Resposta(_nao_sei(f\"apaguei o evento '{titulo}'\", exc), erro=exc)",
        "        if False:\n"
        "            return Resposta(_nao_sei(f\"apaguei o evento '{titulo}'\", exc), erro=exc)",
        "tests/test_registro_ganchos.py::test_falha_depois_de_enviar_e_incerta",
    ),
    Mutacao(
        "chat: erro depois de agir não diz o que já foi feito",
        "src/lifeos/assistant/turno.py",
        "        aviso, nota = registro_texto.aviso_pos_erro(registro.do_turno(turno))",
        '        aviso, nota = "", ""',
        "tests/test_registro_chat.py::test_erro_depois_de_agir_diz_o_que_ja_foi_feito",
    ),
    Mutacao(
        "desfazer: a mesma ação desfeita duas vezes",
        "src/lifeos/registro_sqlite.py",
        '            "WHERE id = ? AND desfeita_em IS NULL AND desfazer IS NOT NULL AND estado = ?",',
        '            "WHERE id = ? AND desfazer IS NOT NULL AND estado = ?",',
        "tests/test_registro.py::test_desfazer_duas_vezes_so_a_primeira_leva",
    ),
    Mutacao(
        "desfazer: `desfaz` alcança ações de outra sessão",
        "src/lifeos/registro_sqlite.py",
        '            "AND substr(turno, 1, ?) = ? ORDER BY id DESC LIMIT 1",',
        '            "AND ? > 0 AND ? IS NOT NULL ORDER BY id DESC LIMIT 1",',
        "tests/test_registro_chat.py::test_desfaz_nao_alcanca_outra_sessao",
    ),
    Mutacao(
        "registro na nuvem: a leitura devolve o que passou dos 30 dias (a TTL apaga com atraso)",
        "src/lifeos/registro_firestore.py",
        "    return sorted((a for a in map(_acao, snaps) if a.criada_em >= corte), key=lambda a: a.id)",
        "    return sorted((a for a in map(_acao, snaps) if corte), key=lambda a: a.id)",
        "tests/test_registro.py::test_o_que_passou_dos_30_dias_nao_volta_por_nenhum_caminho",
    ),
    Mutacao(
        "registro na nuvem: duas ações no mesmo instante, a segunda apaga a primeira",
        "src/lifeos/registro_firestore.py",
        "            _ref(acao_id).create(documento)",
        "            _ref(acao_id).set(documento)",
        "tests/test_registro_firestore.py::test_dois_no_mesmo_nanossegundo_nao_se_sobrescrevem",
    ),
    Mutacao(
        "registro na nuvem: a mesma ação desfeita duas vezes",
        "src/lifeos/registro_firestore.py",
        '        if snap.get("desfeita_em") is not None:\n            return None, None',
        "        if False:\n            return None, None",
        "tests/test_registro.py::test_desfazer_duas_vezes_so_a_primeira_leva",
    ),
    Mutacao(
        "banco: o viking.db abre na nuvem (um banco que some a cada partida)",
        "src/lifeos/banco.py",
        '    if config.STORE == "firestore":\n        raise RuntimeError(',
        "    if False:\n        raise RuntimeError(",
        "tests/test_banco.py::test_na_nuvem_o_sqlite_nao_abre",
    ),
    Mutacao(
        "teto: conferido depois da chamada (a que passa do teto sai)",
        "src/lifeos/custos.py",
        "        if antes is not None:\n            antes()\n        resposta = original(**kwargs)",
        "        resposta = original(**kwargs)\n        if antes is not None:\n            antes()",
        "tests/test_na_nuvem.py::test_teto_no_meio_do_turno_para_antes_da_chamada_seguinte",
    ),
    Mutacao(
        "teto: o dia e o mês contados no UTC, não no fuso do dono",
        "src/lifeos/custos.py",
        "        local = (agora or datetime.now(UTC)).astimezone(self.fuso)",
        "        local = (agora or datetime.now(UTC)).astimezone(UTC)",
        "tests/test_na_nuvem.py::test_o_dia_do_teto_e_o_do_dono_nao_o_do_utc",
    ),
    Mutacao(
        "nuvem: a linha de aprovação vai ao modelo",
        "src/lifeos/assistant/na_nuvem.py",
        "    if local is not None:  # nunca ao modelo, nunca no histórico; a resposta, só ao dono",
        "    if False:  # nunca ao modelo, nunca no histórico; a resposta, só ao dono",
        "tests/test_na_nuvem.py::test_codigo_nao_chega_ao_modelo_nem_ao_historico",
    ),
    Mutacao(
        "barreira: verbo e número numa frase vão ao modelo (Mac e nuvem, D60)",
        "src/lifeos/assistant/agent.py",
        "            if _VERBO.search(linha) and _NUMERO_DE_CODIGO.search(linha):",
        "            if False:",
        "tests/test_gmail_aprovacao.py::test_verbo_com_numero_que_nao_e_codigo_vivo_nao_vai_ao_gemini",
    ),
    Mutacao(
        "nuvem: uma tool do Mac (as finanças) entra no chat da nuvem",
        "src/lifeos/assistant/na_nuvem.py",
        "    navegar_e_executar,\n]",
        "    navegar_e_executar,\n    agent.saldos_das_contas,\n]",
        "tests/test_na_nuvem.py::test_toda_tool_do_mac_decide_onde_mora",
    ),
    Mutacao(
        "nuvem: um turno com erro perde a nota que ia com ele",
        "src/lifeos/assistant/na_nuvem.py",
        "        nota=turno_nucleo.juntar(nota, resultado.nota),",
        "        nota=resultado.nota,",
        "tests/test_na_nuvem.py::test_erro_no_meio_mantem_a_nota_e_o_historico",
    ),
    Mutacao(
        "motor: o /chat roda o turno sem conferir quem pediu",
        "src/lifeos/nuvem/motor.py",
        "    await _quem(request)\n    declarado = ",
        "    declarado = ",
        "tests/test_motor.py::test_chat_sem_token_e_de_outra_conta_nao_chega_ao_turno",
    ),
    Mutacao(
        "motor: corpo sem tamanho declarado passa do teto",
        "src/lifeos/nuvem/motor.py",
        "    if len(corpo) > MAX_CORPO:",
        "    if False:",
        "tests/test_motor.py::test_corpo_em_partes_sem_tamanho_declarado_tambem_tem_teto",
    ),
    Mutacao(
        "nuvem: o serviço do Google abre o login no motor (e pendura o pedido)",
        "src/lifeos/google_auth.py",
        '    if config.STORE == "firestore":  # na nuvem: o token do segredo, e nunca o login',
        "    if False:",
        "tests/test_google_auth.py::test_na_nuvem_o_servico_usa_o_segredo_e_nunca_o_login",
    ),
    Mutacao(
        "nuvem: o segredo é relido a cada uso (um acesso cobrado por chamada)",
        "src/lifeos/config.py",
        "    if caminho not in _SEGREDOS:",
        "    if True:",
        "tests/test_google_auth.py::test_segredo_e_lido_uma_vez_e_vazio_erra_sem_mostrar",
    ),
    Mutacao(
        "chat da nuvem: um erro de rede apaga a conversa e a nota",
        "src/lifeos/nuvem/chat_cliente.py",
        "            continue  # a conversa e a nota ficam como estavam: o turno não entrou",
        '            historico, nota = [], ""\n            continue',
        "tests/test_chat_nuvem_cliente.py::test_erro_de_rede_nao_perde_a_conversa_nem_a_nota",
    ),
    Mutacao(
        "chat da nuvem: o texto da rede chega cru ao terminal",
        "src/lifeos/nuvem/chat_cliente.py",
        '    return limpar_controles(valor) if isinstance(valor, str) else ""',
        '    return valor if isinstance(valor, str) else ""',
        "tests/test_chat_nuvem_cliente.py::test_texto_da_rede_sai_sem_controle_de_terminal",
    ),
    Mutacao(
        "chat da nuvem: o cliente desiste antes do motor (e repete o que ele fez)",
        "src/lifeos/nuvem/cliente.py",
        '    return _chamar(sessao, "POST", "/chat", corpo=pedido, prazo=PRAZO_CHAT_S)',
        '    return _chamar(sessao, "POST", "/chat", corpo=pedido, prazo=PRAZO_S)',
        "tests/test_nuvem_cliente.py::test_turno_de_chat_vai_por_post_com_a_conversa_no_corpo_e_o_prazo_longo",
    ),
    Mutacao(
        "segredos: o valor sobe pelo argv (aparece em ps e no histórico)",
        "scripts/nuvem.py",
        '        _gcloud(ctx, "secrets", "versions", "add", nome, "--data-file=-"), entrada=valor',
        '        _gcloud(ctx, "secrets", "versions", "add", nome, f"--data-file={valor}"), entrada=None',
        "tests/test_nuvem_script.py::test_segredo_sobe_pela_entrada_padrao_e_nunca_aparece",
    ),
    Mutacao(
        "segredos: o deploy entrega o segredo como variável de ambiente",
        "scripts/nuvem.py",
        '            "--set-secrets=" + ",".join(f"{s.caminho}={s.nome}:latest" for s in montados),',
        '            "--set-secrets=" + ",".join(f"{s.variavel}={s.nome}:latest" for s in montados),',
        "tests/test_nuvem_script.py::test_deploy_entrega_os_segredos_so_como_volume_e_o_prazo_do_turno",
    ),
    Mutacao(
        "segredos: a leitura é dada no projeto inteiro, não em cada segredo",
        "scripts/nuvem.py",
        '            "secrets",\n            "add-iam-policy-binding",\n            s.nome,',
        '            "projects",\n            "add-iam-policy-binding",\n            ctx.projeto,',
        "tests/test_nuvem_script.py::test_a_leitura_do_segredo_e_dada_em_cada_segredo_nao_no_projeto",
    ),
    Mutacao(
        "segredos: a prova aceita segredo no ambiente do motor",
        "scripts/nuvem.py",
        '        "valueFrom" in v for v in variaveis.values()',
        "        False for v in variaveis.values()",
        "tests/test_nuvem_script.py::test_a_prova_recusa_segredo_no_ambiente",
    ),
    Mutacao(
        "segredos: sobe um token da agenda que não renova",
        "scripts/nuvem.py",
        '    if not info.get("refresh_token") or "https://www.googleapis.com/auth/calendar" not in escopos:',
        "    if False:",
        "tests/test_nuvem_script.py::test_token_da_agenda_que_nao_renova_nao_sobe",
    ),
    Mutacao(
        "nuvem.py: passo não medido afirma que o recurso falta",
        "scripts/nuvem.py",
        '            seta = "→" if estado.medido else "?→"',
        '            seta = "→"',
        "tests/test_nuvem_script.py::test_passo_nao_medido_nao_afirma_que_falta",
    ),
    Mutacao(
        "desfazer: a cópia recriada leva os convidados (e-mail em nome do dono)",
        "src/lifeos/calendar/service.py",
        '    "summary",\n    "description",\n    "location",',
        '    "summary",\n    "attendees",\n    "description",\n    "location",',
        "tests/test_registro_chat.py::test_desfaz_recria_sem_convidados_quando_o_evento_sumiu",
    ),
    Mutacao(
        "desfazer: volta o horário mesmo se alguém mudou depois",
        "src/lifeos/calendar/service.py",
        '        _mesmo_horario(atual.get("start"), copia["novo_start"])',
        '        True or _mesmo_horario(atual.get("start"), copia["novo_start"])',
        "tests/test_registro_chat.py::test_desfaz_nao_mexe_se_o_horario_mudou_depois",
    ),
    Mutacao(
        "desfazer: resposta ambígua devolve o desfazer (e a cópia sai duas vezes)",
        "src/lifeos/calendar/service.py",
        '        if not getattr(exc, "incerta", False):\n            registro.devolver_desfazer(acao_id)',
        "        if True:\n            registro.devolver_desfazer(acao_id)",
        "tests/test_registro_chat.py::test_desfazer_ambiguo_nao_recria_duas_vezes",
    ),
    Mutacao(
        "aprovar: o início volta a ser comparado como texto (outro fuso = 'mudou')",
        "src/lifeos/calendar/service.py",
        '        or not _mesmo_instante(_evento_de(atual).inicio, dados["inicio"])',
        '        or _evento_de(atual).inicio != dados["inicio"]',
        "tests/test_mcp_aprovacao.py::test_fuso_do_dono_diferente_na_aprovacao_nao_e_mudanca",
    ),
    Mutacao(
        "aprovar: qualquer horário é o mesmo instante (evento que andou é mexido)",
        "src/lifeos/calendar/service.py",
        "        return (da.tzinfo is None) == (db.tzinfo is None) and da == db",
        "        return True",
        "tests/test_mcp_aprovacao.py::test_evento_que_andou_uma_hora_com_a_mesma_versao_nao_e_mexido",
    ),
    Mutacao(
        "instante: dia inteiro vale o mesmo que a meia-noite",
        "src/lifeos/calendar/service.py",
        "    return not com_hora_a and not com_hora_b and da == db",
        "    return da == db",
        "tests/test_mcp_aprovacao.py::test_mesmo_instante",
    ),
    Mutacao(
        "google-genai: tool com anotação que só o conversor de reserva aceita",
        "src/lifeos/assistant/agent.py",
        "def concluir_lembrete(reminder_id: str) -> str:",
        "def concluir_lembrete(reminder_id: tuple[int, str]) -> str:",
        "tests/test_assistant_tools.py::test_schema_aceito_pela_api_do_gemini",
    ),
    Mutacao(
        "docstring: navegar perde 'nunca uma pergunta' (antes, 'AÇÃO' bastava)",
        "src/lifeos/assistant/agent.py",
        '    `objetivo` é sempre uma AÇÃO ("abrir X", "buscar Y e abrir o primeiro resultado"), nunca uma\n'
        "    pergunta: o executor",
        '    `objetivo` é sempre uma AÇÃO ("abrir X", "buscar Y e abrir o primeiro resultado"), sempre\n'
        "    curto: o executor",
        "tests/test_assistant_tools.py::test_regras_de_comportamento_sobrevivem_a_compressao",
    ),
    Mutacao(
        "CI: instala a versão do dia, não a do lock",
        ".github/workflows/testes.yml",
        "        run: uv sync --locked --extra dev",
        "        run: uv sync --extra dev",
        "tests/test_ci_workflow.py::test_instala_so_o_que_esta_no_lock",
    ),
    Mutacao(
        "CI: action puxada por tag (o conteúdo pode mudar sem o commit mudar)",
        ".github/workflows/testes.yml",
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "      - uses: actions/checkout@v7",
        "tests/test_ci_workflow.py::test_toda_action_fixada_por_sha",
    ),
    Mutacao(
        "CI: o token do job ganha escrita no repo",
        ".github/workflows/testes.yml",
        "  contents: read",
        "  contents: write",
        "tests/test_ci_workflow.py::test_permissao_so_de_leitura",
    ),
    Mutacao(
        "CI: o scanner ignora uma falha sem decisão",
        ".github/workflows/testes.yml",
        "--disable-pip --progress-spinner off\n",
        "--disable-pip --progress-spinner off --ignore-vuln PYSEC-2026-3552\n",
        "tests/test_ci_workflow.py::test_scanner_nao_ignora_nenhuma_falha",
    ),
    Mutacao(
        "formato: trecho do texto entra no HTML sem escape",
        "src/lifeos/gmail/formato.py",
        "        escapado = html.escape(texto)",
        "        escapado = texto",
        "tests/test_gmail_formato.py::test_nada_do_texto_vira_marcacao",
    ),
    Mutacao(
        "formato: a parte texto mantém os asteriscos",
        "src/lifeos/gmail/formato.py",
        '    return "".join(texto for _estilo, texto in _trechos(linha))',
        "    return linha",
        "tests/test_gmail_formato.py::test_o_email_da_captura_sai_formatado",
    ),
    Mutacao(
        "formato: itálico pega asterisco colado a letra (2*3*4)",
        "src/lifeos/gmail/formato.py",
        r'_ITALICO = re.compile(r"(?<![\w*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![\w*])")',
        r'_ITALICO = re.compile(r"(?<![*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![*])")',
        "tests/test_gmail_formato.py::test_vizinhos_legitimos_ficam_como_estao",
    ),
    Mutacao(
        "formato: o HTML sai de outro campo que não o corpo aprovado",
        "src/lifeos/gmail/envio.py",
        '        formato.documento(rascunho.corpo, assinatura=ASSINATURA), subtype="html"',
        '        formato.documento(rascunho.assunto, assinatura=ASSINATURA), subtype="html"',
        "tests/test_gmail_envio.py::test_as_duas_partes_saem_do_texto_aprovado",
    ),
    Mutacao(
        "formato: o aviso do terminal aparece sem formatação",
        "src/lifeos/gmail/tools.py",
        "    if formato.tem_formatacao(r.corpo):",
        "    if True:",
        "tests/test_gmail_envio_chat.py::test_o_terminal_mostra_o_texto_fonte_e_avisa_da_formatacao",
    ),
    Mutacao(
        "agenda: a busca ignora as páginas seguintes",
        "src/lifeos/calendar/service.py",
        '        pagina = resposta.get("nextPageToken")',
        "        pagina = None",
        "tests/test_calendar_service.py::test_busca_com_300_ocorrencias_vem_inteira",
    ),
    Mutacao(
        "agenda: parar no teto diz que veio inteira",
        "src/lifeos/calendar/service.py",
        "            return Eventos(eventos[:TETO_EVENTOS], completa=False)",
        "            return Eventos(eventos[:TETO_EVENTOS], completa=True)",
        "tests/test_calendar_service.py::test_busca_acima_do_teto_para_e_diz_que_esta_incompleta",
    ),
    Mutacao(
        "agenda: o texto não avisa que a lista parou no teto",
        "src/lifeos/calendar/tools.py",
        "    if eventos.completa:",
        "    if True:",
        "tests/test_calendar_tools.py::test_busca_incompleta_diz_que_ha_mais",
    ),
    Mutacao(
        "agenda: o MCP diz completa sem perguntar",
        "src/lifeos/mcp_server/server.py",
        '            "completa": resposta.dados.completa,',
        '            "completa": True,',
        "tests/test_mcp_server.py::test_lista_acima_do_teto_diz_que_esta_incompleta",
    ),
    Mutacao(
        "envelope: contexto do campo sai sem redação",
        "src/lifeos/browser/_jev_subprocess.py",
        "        return field_context(goal, action, _redigida(page), history)",
        "        return field_context(goal, action, page, history)",
        "tests/test_jev_subprocess_main.py::test_field_context_tambem_passa_pelo_envelope",
    ),
    Mutacao(
        "contador: conta a página já redigida (nunca acha nada)",
        "src/lifeos/browser/_jev_subprocess.py",
        "        contagem = _redacao.escondidos(page, redigida)",
        "        contagem = _redacao.escondidos(redigida, redigida)",
        "tests/test_jev_subprocess_main.py::test_o_envelope_conta_o_que_escondeu_dos_modelos",
    ),
    Mutacao(
        "contador: marca que a página já tinha conta como escondida",
        "src/lifeos/browser/_redacao.py",
        "            trocados = depois.count(marca) - antes.count(marca)",
        "            trocados = depois.count(marca)",
        "tests/test_jev_subprocess_main.py::test_marca_que_a_pagina_ja_tinha_nao_conta",
    ),
    Mutacao(
        "contador: soma os passos em vez do máximo",
        "src/lifeos/browser/jev_runner.py",
        "                maximo[tipo] = max(maximo.get(tipo, 0), quantos)",
        "                maximo[tipo] = maximo.get(tipo, 0) + quantos",
        "tests/test_browser_seguranca.py::test_o_resultado_leva_o_maximo_por_tipo_nao_a_soma",
    ),
    Mutacao(
        "agenda: acabar as páginas permitidas diz que veio inteira",
        "src/lifeos/calendar/service.py",
        "    return Eventos(eventos, completa=False)",
        "    return Eventos(eventos, completa=True)",
        "tests/test_calendar_service.py::test_paginas_vazias_sem_fim_param_e_dizem_que_esta_incompleta",
    ),
    # --- Sessão 9: o banco, os lembretes e o envio ------------------------------------------
    Mutacao(
        "banco: sem a trava de escrita desde o começo (DEFERRED)",
        "src/lifeos/banco.py",
        '    conn.execute("BEGIN IMMEDIATE")',
        '    conn.execute("BEGIN DEFERRED")',
        "tests/test_banco_migracoes.py::test_a_trava_de_escrita_vem_no_begin",
    ),
    Mutacao(
        "banco: falha no meio comita o que já rodou",
        "src/lifeos/banco.py",
        '        if conn.in_transaction:\n            conn.execute("ROLLBACK")',
        '        if conn.in_transaction:\n            conn.execute("COMMIT")',
        "tests/test_banco_migracoes.py::test_falha_no_meio_de_um_banco_de_hoje_deixa_o_banco_como_estava",
    ),
    Mutacao(
        "banco: passos com executescript (comita sozinho)",
        "src/lifeos/banco.py",
        "            for comando in self.passo:\n                conn.execute(comando)",
        '            conn.executescript(";\\n".join(self.passo))',
        "tests/test_banco_migracoes.py::test_falha_no_meio_de_um_banco_de_hoje_deixa_o_banco_como_estava",
    ),
    Mutacao(
        "banco: não relê o ledger depois da trava",
        "src/lifeos/banco.py",
        "    if not _pendentes(conn):\n"
        "        return  # o caminho de toda abertura: uma leitura do ledger, sem trava\n"
        '    conn.execute("BEGIN IMMEDIATE")\n'
        "    try:\n"
        "        pendentes = _pendentes(conn)  # relido com a trava: outro processo pode ter migrado",
        "    pendentes = _pendentes(conn)\n"
        "    if not pendentes:\n"
        "        return\n"
        '    conn.execute("BEGIN IMMEDIATE")\n'
        "    try:\n"
        "        pass",
        "tests/test_banco_migracoes.py::test_outro_processo_migra_entre_a_leitura_e_a_trava",
    ),
    Mutacao(
        "banco: abre um banco migrado por versão mais nova",
        "src/lifeos/banco.py",
        "    if desconhecidas := sorted(set(aplicadas) - set(conhecidas)):",
        "    if desconhecidas := []:",
        "tests/test_banco_migracoes.py::test_banco_migrado_por_versao_mais_nova_nao_abre",
    ),
    Mutacao(
        "banco: não confere o checksum das aplicadas",
        "src/lifeos/banco.py",
        "        if conhecidas[numero].checksum != checksum:",
        "        if False:",
        "tests/test_banco_migracoes.py::test_migracao_editada_depois_de_aplicada_nao_abre",
    ),
    Mutacao(
        "banco: migra sem o backup",
        "src/lifeos/banco.py",
        "            _copiar(pendentes[0].numero)",
        "            pass",
        "tests/test_banco_migracoes.py::test_backup_antes_de_migrar_um_banco_com_dados",
    ),
    Mutacao(
        "cli: banco mais novo vira traceback",
        "src/lifeos/cli.py",
        "    except banco.ErroDeBanco as exc:",
        "    except ZeroDivisionError as exc:",
        "tests/test_banco_migracoes.py::test_viking_com_banco_mais_novo_diz_o_que_fazer_e_sai_com_1",
    ),
    Mutacao(
        "testes: cada teste sem o próprio banco",
        "tests/conftest.py",
        '    monkeypatch.setattr("lifeos.banco.CAMINHO", tmp_path / "viking.db")',
        "    pass",
        "tests/test_banco.py::test_cada_teste_tem_o_proprio_banco",
    ),
    Mutacao(
        "store: a reserva ignora a reserva viva de outra execução",
        "src/lifeos/reminders/store.py",
        '            "AND (envio_reservado_ate IS NULL OR envio_reservado_ate <= ?)",',
        '            "AND ? IS NOT NULL",',
        "tests/test_reminders_contrato.py::test_so_uma_execucao_ganha_a_reserva",
    ),
    Mutacao(
        "store: concluir de novo muda a hora",
        "src/lifeos/reminders/store.py",
        '            "WHERE id = ? AND completed_at IS NULL",',
        '            "WHERE id = ?",',
        "tests/test_reminders_contrato.py::test_concluir_de_novo_nao_muda_a_hora",
    ),
    Mutacao(
        "store: horário sem fuso é aceito",
        "src/lifeos/reminders/store.py",
        "    if momento.tzinfo is None or momento.utcoffset() is None:",
        "    if False:",
        "tests/test_reminders_contrato.py::test_horario_sem_fuso_e_recusado_e_nada_e_gravado",
    ),
    Mutacao(
        "store: add repetido sobrescreve o que existe",
        "src/lifeos/reminders/store.py",
        '            "metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "\n'
        '            "ON CONFLICT (id) DO NOTHING",',
        '            "metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "\n'
        '            "ON CONFLICT (id) DO UPDATE SET title = excluded.title",',
        "tests/test_reminders_contrato.py::test_add_repetido_com_o_mesmo_id_nao_duplica",
    ),
    Mutacao(
        "lembretes: horário sem fuso vira o do relógio da máquina",
        "src/lifeos/reminders/service.py",
        "    return prazo if prazo.tzinfo is not None else prazo.replace(tzinfo=config.TIMEZONE)",
        "    return prazo if prazo.tzinfo is not None else prazo.astimezone()",
        "tests/test_reminders_service.py::test_criar_lembrete_com_quando_data_e_hora",
    ),
    Mutacao(
        "lembretes: a janela não para em 24 h",
        "src/lifeos/reminders/envio.py",
        "    vencidos = store.vencidos(agora - JANELA, agora)",
        "    vencidos = store.vencidos(agora - 1000 * JANELA, agora)",
        "tests/test_lembretes_envio.py::test_vencido_ha_mais_de_24h_nao_sai_e_e_listado",
    ),
    Mutacao(
        "lembretes: 'pode ter saído' solta a reserva e reenvia",
        "src/lifeos/reminders/envio.py",
        "            store.marcar_envio(lembrete.id, por=execucao, estado=interface.INCERTO, agora=agora)",
        "            store.soltar_envio(lembrete.id, por=execucao)",
        "tests/test_lembretes_envio.py::test_falha_que_pode_ter_enviado_nao_reenvia",
    ),
    Mutacao(
        "limpeza: sem o limite de 1 s",
        "scripts/limpar_lembretes_de_teste.py",
        "- datetime.fromisoformat(criado) < LIMITE",
        "- datetime.fromisoformat(criado) < LIMITE * 100000",
        "tests/test_script_limpar_lembretes.py::test_aplicar_apaga_so_o_lixo",
    ),
    Mutacao(
        "firestore: reserva viva de outra execução é ignorada",
        "src/lifeos/reminders/store_firestore.py",
        "        if reservado_ate is not None and reservado_ate > agora:",
        "        if False:",
        "tests/test_reminders_contrato.py::test_so_uma_execucao_ganha_a_reserva",
    ),
    Mutacao(
        "firestore: grava sem a precondição (a escrita velha passa por cima)",
        "src/lifeos/firestore_comum.py",
        "            ref.update(mudanca, option=opcao)",
        "            ref.update(mudanca)",
        "tests/test_store_firestore.py::test_quem_leu_antes_de_outro_gravar_rele_e_decide_de_novo",
    ),
    Mutacao(
        "firestore: add repetido sobrescreve o que existe",
        "src/lifeos/reminders/store_firestore.py",
        "        ref.create(\n            _documento(",
        "        ref.set(\n            _documento(",
        "tests/test_reminders_contrato.py::test_add_repetido_com_o_mesmo_id_nao_duplica",
    ),
    Mutacao(
        "firestore: id que não é UUID vira caminho",
        "src/lifeos/reminders/store_firestore.py",
        "    if not interface.id_valido(reminder_id):\n        return None",
        "    if False:\n        return None",
        "tests/test_reminders_contrato.py::test_id_que_nao_e_uuid_e_recusado_e_nao_alcanca_nada",
    ),
    Mutacao(
        "sqlite: id que não é UUID é aceito",
        "src/lifeos/reminders/store.py",
        "    if not interface.id_valido(reminder_id):",
        "    if False:",
        "tests/test_reminders_contrato.py::test_id_que_nao_e_uuid_e_recusado_e_nao_alcanca_nada",
    ),
    Mutacao(
        "motor: o token é lido sem conferir a assinatura",
        "src/lifeos/nuvem/motor.py",
        "    dados = dict(id_token.verify_token(token, requisicao, audience=config.NUVEM_URL))",
        '    dados = dict(__import__("google.auth.jwt", fromlist=["x"]).decode(token, verify=False))',
        "tests/test_motor.py::test_token_que_nao_vale_401",
    ),
    Mutacao(
        "motor: qualquer emissor serve",
        "src/lifeos/nuvem/motor.py",
        '    if dados.get("iss") not in EMISSORES:',
        "    if False:",
        "tests/test_motor.py::test_token_que_nao_vale_401",
    ),
    Mutacao(
        "motor: qualquer conta com token válido entra",
        "src/lifeos/nuvem/motor.py",
        '    if not dados.get("email_verified") or email not in quem_pode(request.url.path):',
        '    if not dados.get("email_verified"):',
        "tests/test_motor.py::test_token_valido_de_quem_nao_pode_403",
    ),
    Mutacao(
        "nuvem.py: gcloud sem o projeto do Viking passa",
        "scripts/nuvem.py",
        '    if comando[0] != "gcloud" or not any(a.startswith("--project=") for a in comando):',
        '    if comando[0] != "gcloud":',
        "tests/test_nuvem_script.py::test_rodar_recusa_comando_sem_o_projeto",
    ),
    Mutacao(
        "nuvem.py: publica commit sujo, fora do GitHub ou com CI vermelho",
        "scripts/nuvem.py",
        "        if not pode:",
        "        if False:",
        "tests/test_nuvem_script.py::test_deploy_recusa_o_que_nao_e_um_commit_verde",
    ),
    Mutacao(
        "cliente: a cota da impersonação cai no projeto padrão do gcloud",
        "src/lifeos/nuvem/cliente.py",
        "        dono = dono.with_quota_project(config.NUVEM_PROJETO)",
        "        dono = dono",
        "tests/test_nuvem_cliente.py::test_o_token_e_do_viking_cli_com_audience_e_cota_no_viking",
    ),
    Mutacao(
        "cliente: horário sem fuso vindo da nuvem é aceito",
        "src/lifeos/nuvem/cliente.py",
        "    if momento.tzinfo is None:  # a nuvem só manda instantes; sem fuso seria adivinhar",
        "    if False:",
        "tests/test_nuvem_cliente.py::test_cada_falha_vira_uma_linha_e_saida_1",
    ),
    Mutacao(
        "firestore: documento nasce sem os campos nulos",
        "src/lifeos/reminders/store_firestore.py",
        "    documento = dict.fromkeys(_CAMPOS)",
        "    documento = {}",
        "tests/test_store_firestore.py::test_todo_documento_tem_todos_os_campos_em_cada_passo",
    ),
    Mutacao(
        "confirmação firestore: proposta nova não invalida a velha",
        "src/lifeos/confirmacao_firestore.py",
        "    if substituir:\n        cancelar(acao)",
        "    if False:\n        cancelar(acao)",
        "tests/test_confirmacao.py::test_proposta_nova_invalida_o_codigo_velho",
    ),
    Mutacao(
        "confirmação firestore: a reserva do código sobrescreve a de outro",
        "src/lifeos/confirmacao_firestore.py",
        '        ref.create({"codigo": codigo, "reservado_ate": ate})',
        '        ref.set({"codigo": codigo, "reservado_ate": ate})',
        "tests/test_confirmacao.py::test_varias_propostas_ao_mesmo_tempo_nunca_repetem_o_codigo",
    ),
    Mutacao(
        "confirmação firestore: gastar sem comparar e trocar",
        "src/lifeos/confirmacao_firestore.py",
        "    if not firestore_comum.trocar(ref, decidir):",
        '    if ref.update({"estado": CONSUMIDA, "consumida_em": agora}) and False:',
        "tests/test_confirmacao.py::test_mesmo_codigo_gasto_por_varios_ao_mesmo_tempo_so_um_leva",
    ),
    Mutacao(
        "confirmação firestore: o código gasto não fica reservado pela janela de uso",
        "src/lifeos/confirmacao_firestore.py",
        '    _codigo_ref(snap.get("codigo")).set(\n',
        "    (lambda _dados: None)(\n",
        "tests/test_confirmacao.py::test_codigo_usado_reserva_pela_janela_do_desfazer",
    ),
    Mutacao(
        "confirmação: o limite de tentativas erradas afrouxa",
        "src/lifeos/confirmacao.py",
        "TENTATIVAS = 3  #",
        "TENTATIVAS = 4  #",
        "tests/test_confirmacao.py::test_a_terceira_errada_cancela_e_a_segunda_nao",
    ),
    Mutacao(
        "confirmação sqlite: tentativa errada não conta",
        "src/lifeos/confirmacao_sqlite.py",
        '"UPDATE confirmacoes SET erros = erros + 1 "',
        '"UPDATE confirmacoes SET erros = erros + 0 "',
        "tests/test_confirmacao.py::test_a_terceira_errada_cancela_e_a_segunda_nao",
    ),
    Mutacao(
        "confirmação firestore: tentativa errada não conta",
        "src/lifeos/confirmacao_firestore.py",
        '            erros = int(snap.get("erros")) + 1',
        '            erros = int(snap.get("erros")) + 0',
        "tests/test_confirmacao.py::test_a_terceira_errada_cancela_e_a_segunda_nao",
    ),
    Mutacao(
        "confirmação: código errado não conta nas abertas",
        "src/lifeos/confirmacao.py",
        "    restam = _STORE.errar(acao, agora=agora, limite=TENTATIVAS)",
        "    restam = None",
        "tests/test_confirmacao.py::test_a_terceira_errada_cancela_e_a_segunda_nao",
    ),
    Mutacao(
        "confirmação sqlite: propor lê os reservados fora da transação",
        "src/lifeos/confirmacao_sqlite.py",
        '        conn.execute("BEGIN IMMEDIATE")',
        "        pass",
        "tests/test_confirmacao.py::test_varias_propostas_ao_mesmo_tempo_nunca_repetem_o_codigo",
    ),
    Mutacao(
        "ao_dono: na nuvem, sem o coletor, imprime (o stdout é o log)",
        "src/lifeos/ao_dono.py",
        '    if config.STORE == "firestore":\n        raise SemCanal',
        "    if False:\n        raise SemCanal",
        "tests/test_na_nuvem_gmail.py::test_na_nuvem_sem_coletor_mostrar_erra_alto_e_nao_imprime",
    ),
    Mutacao(
        "gmail: o código da proposta volta a sair por print",
        "src/lifeos/gmail/tools.py",
        "    ao_dono.mostrar(texto)",
        "    print(texto, flush=True)",
        "tests/test_na_nuvem_gmail.py::test_o_codigo_da_limpeza_so_volta_no_campo_ao_dono",
    ),
    Mutacao(
        "nuvem: a resposta da barreira volta no texto, fora do campo ao_dono",
        "src/lifeos/assistant/na_nuvem.py",
        "        ao_dono.mostrar(texto)\n"
        "        juntas = turno_nucleo.juntar(nota, nota_nova)\n"
        "        return _resposta(historico=historico_json, nota=juntas, teto=teto, "
        "so_ao_dono=so_ao_dono)",
        "        juntas = turno_nucleo.juntar(nota, nota_nova)\n"
        "        return _resposta(historico=historico_json, nota=juntas, teto=teto, "
        "so_ao_dono=so_ao_dono, resposta=texto)",
        "tests/test_na_nuvem_gmail.py::test_aprovar_pela_nuvem_arquiva_sem_passar_pelo_modelo",
    ),
    Mutacao(
        "nuvem: a barreira não aprova (sem o laço do Mac)",
        "src/lifeos/assistant/na_nuvem.py",
        "    local = agent.aprovacao_local(linha)",
        "    local = None",
        "tests/test_na_nuvem_gmail.py::test_aprovar_pela_nuvem_arquiva_sem_passar_pelo_modelo",
    ),
    Mutacao(
        "nuvem: só o número, sem proposta aberta, vai ao modelo",
        "src/lifeos/assistant/na_nuvem.py",
        '        return agent.NAO_E_CODIGO_AQUI, ""',
        "        return None",
        "tests/test_na_nuvem.py::test_linha_com_cara_de_aprovacao_nunca_vai_ao_modelo",
    ),
    Mutacao(
        "limpeza: pela nuvem, sem terminal, a proposta nasce",
        "src/lifeos/gmail/limpeza.py",
        "    if ao_dono.pela_rede() and not ao_dono.interativo():",
        "    if False:",
        "tests/test_na_nuvem_gmail.py::test_sem_terminal_a_limpeza_nao_propoe_nem_le_o_gmail",
    ),
    Mutacao(
        "envio: o terminal declarado pelo Mac é ignorado",
        "src/lifeos/gmail/envio.py",
        "    return ao_dono.interativo()",
        "    return True",
        "tests/test_na_nuvem_gmail.py::test_sem_terminal_o_envio_a_outra_pessoa_nao_propoe",
    ),
    Mutacao(
        "ao_dono: o que o terminal do Mac declarou não vale",
        "src/lifeos/ao_dono.py",
        "    if declarado is not None:\n        return declarado",
        "    if False:\n        return declarado",
        "tests/test_na_nuvem_gmail.py::test_o_codigo_da_limpeza_so_volta_no_campo_ao_dono",
    ),
    Mutacao(
        "prazo: a espera do Gmail começa sem caber no turno",
        "src/lifeos/gmail/service.py",
        "    _no_prazo(segundos + REDE_S)\n    _dormir(segundos)",
        "    _dormir(segundos)",
        "tests/test_prazo.py::test_gmail_recusando_sempre_nao_passa_do_prazo",
    ),
    Mutacao(
        "prazo: o pedido ao Gmail sai sem caber no turno",
        "src/lifeos/gmail/service.py",
        "        _no_prazo(REDE_S)\n        _COTA.gastar(custo)",
        "        _COTA.gastar(custo)",
        "tests/test_prazo.py::test_pedido_que_nao_cabe_no_prazo_nao_sai",
    ),
    Mutacao(
        "prazo: o lote de leitura sai sem caber no turno",
        "src/lifeos/gmail/service.py",
        "            _no_prazo(REDE_S)\n            _COTA.gastar(CUSTO_GET",
        "            _COTA.gastar(CUSTO_GET",
        "tests/test_prazo.py::test_lote_de_leitura_que_nao_cabe_no_prazo_nao_sai",
    ),
    Mutacao(
        "prazo: a espera do orçamento de cota ignora o turno",
        "src/lifeos/gmail/service.py",
        "            _esperar(max(espera, 0.01))",
        "            _dormir(max(espera, 0.01))",
        "tests/test_prazo.py::test_espera_do_orcamento_que_nao_cabe_nem_comeca",
    ),
    Mutacao(
        "prazo: a chamada ao modelo sai sem caber no turno",
        "src/lifeos/assistant/na_nuvem.py",
        '    prazo.conferir(PRAZO_DO_GEMINI_MS / 1000, "a próxima chamada ao modelo")',
        "    pass",
        "tests/test_prazo.py::test_a_chamada_ao_modelo_que_nao_cabe_nao_sai",
    ),
    Mutacao(
        "prazo: o turno da nuvem roda sem prazo",
        "src/lifeos/assistant/na_nuvem.py",
        "    with ao_dono.coletar(interativo=interativo) as so_ao_dono, prazo.ate(PRAZO_DO_TURNO_S):",
        "    with ao_dono.coletar(interativo=interativo) as so_ao_dono:",
        "tests/test_prazo.py::test_turno_que_agiu_e_ficou_sem_tempo_diz_o_que_fez",
    ),
    Mutacao(
        "nuvem.py: o script exige o extra nuvem (o Mac não o tem)",
        "scripts/nuvem.py",
        "import argparse\n",
        "import argparse\nimport google.cloud.firestore  # noqa: F401\n",
        "tests/test_nuvem_script.py::test_o_script_abre_no_mac_sem_o_extra_nuvem",
    ),
    Mutacao(
        "prazo: o aviso de espera do Gmail vai ao log da nuvem",
        "src/lifeos/gmail/service.py",
        '    if config.STORE == "firestore":\n        return\n    print(texto, file=sys.stderr',
        "    print(texto, file=sys.stderr",
        "tests/test_prazo.py::test_aviso_de_espera_so_no_terminal_do_mac",
    ),
    Mutacao(
        "nuvem.py: o token do Gmail fica fora dos segredos do motor",
        "scripts/nuvem.py",
        "    Segredo(\n"
        '        "viking-gmail", "/segredos/gmail/token.json", "VIKING_GMAIL_TOKEN_ARQUIVO", '
        "do_mac=True\n"
        "    ),\n",
        "",
        "tests/test_nuvem_script.py::test_todo_arquivo_de_segredo_que_o_config_le_tem_um_segredo_no_deploy",
    ),
    Mutacao(
        "nuvem.py: publica com um segredo vazio (a revisão cairia)",
        "scripts/nuvem.py",
        "            if faltam:",
        "            if False:",
        "tests/test_nuvem_script.py::test_deploy_nao_publica_com_um_segredo_vazio_que_nao_e_do_mac",
    ),
    Mutacao(
        "nuvem.py: sobe um token do Gmail (ou do Drive) sem a permissão certa",
        "scripts/nuvem.py",
        '    if not info.get("refresh_token") or escopo not in escopos:',
        '    if not info.get("refresh_token"):',
        "tests/test_nuvem_script.py::test_token_do_gmail_torto_nao_sobe_nem_aparece",
    ),
    Mutacao(
        "cliente: mostra o que só o dono vê sem terminal interativo",
        "src/lifeos/nuvem/chat_cliente.py",
        "        if so_seu and ao_dono.interativo():",
        "        if so_seu:",
        "tests/test_chat_nuvem_cliente.py::test_ao_dono_aparece_so_num_terminal_interativo",
    ),
    Mutacao(
        "google_auth: token da nuvem sem conferir a permissão",
        "src/lifeos/google_auth.py",
        "            if not set(scopes) <= set(gravados):",
        "            if False:",
        "tests/test_google_auth.py::test_na_nuvem_o_gmail_usa_o_segredo_dele",
    ),
    Mutacao(
        "motor: a fumaça diz que o token do Gmail renova quando ele falhou",
        "src/lifeos/nuvem/motor.py",
        '        log.warning("segredo do gmail: %s", type(exc).__name__)',
        '        resposta["gmail"] = True',
        "tests/test_motor.py::test_fumaca_dos_segredos_so_diz_se_le",
    ),
    # --- Sessão 11 (D61), C1: o Gmail opcional na nuvem e a identidade por rota ---------------
    Mutacao(
        "nuvem.py: o deploy monta o segredo do Gmail sem versão (a revisão cairia)",
        "scripts/nuvem.py",
        "    montados = tuple(s for s in SEGREDOS if _versoes(ctx, s.nome))",
        "    montados = SEGREDOS",
        "tests/test_nuvem_script.py::test_deploy_sem_o_token_do_gmail_publica_sem_ele",
    ),
    Mutacao(
        "nuvem.py: o token do Gmail que subiu não pede revisão nova",
        "scripts/nuvem.py",
        "        and agora.volumes_no_ar == {s.nome for s in montados}",
        "        and True",
        "tests/test_nuvem_script.py::test_o_token_do_gmail_que_subiu_pede_revisao_mesmo_sem_codigo_novo",
    ),
    Mutacao(
        "nuvem.py: a prova dos volumes aceita um segredo a mais montado",
        "scripts/nuvem.py",
        "    certos = volumes == {s.nome for s in montados}",
        "    certos = {s.nome for s in montados} <= volumes",
        "tests/test_nuvem_script.py::test_a_prova_dos_volumes_compara_com_os_montados",
    ),
    Mutacao(
        "na_nuvem: as tools do Gmail sem o token do Gmail",
        "src/lifeos/assistant/na_nuvem.py",
        "    if config.gmail_no_motor():",
        "    if True:",
        "tests/test_na_nuvem.py::test_sem_o_token_do_gmail_a_nuvem_nao_tem_as_tools_dele",
    ),
    Mutacao(
        "motor: toda conta do Viking entra em toda rota",
        "src/lifeos/nuvem/motor.py",
        "    contas = QUEM_FALA.get(rota, frozenset())",
        "    contas = frozenset({CLI, MAOS, AGENDADOR})",
        "tests/test_motor.py::test_as_maos_e_o_agendador_nao_entram_nas_portas_do_terminal",
    ),
    Mutacao(
        "turno: o texto de sistema ignora onde o chat roda",
        "src/lifeos/assistant/turno.py",
        '    presentes = {f.__name__ for f in ferramentas} | ({_NUVEM} if onde == "nuvem" else set())',
        "    presentes = {f.__name__ for f in ferramentas}",
        "tests/test_na_nuvem.py::test_os_textos_de_antes_nao_mudam_nem_num_byte",
    ),
    Mutacao(
        "chat_cliente: a abertura promete o Gmail que a nuvem não tem",
        "src/lifeos/nuvem/chat_cliente.py",
        '    (tem if capacidades.get("gmail") is True else so_no_mac).append("Gmail")',
        '    tem.append("Gmail")',
        "tests/test_chat_nuvem_cliente.py::test_a_abertura_nao_promete_o_gmail_que_nao_esta_la",
    ),
    # --- Sessão 11 (D61), C2: a fila das mãos e o navegador no chat da nuvem ------------------
    Mutacao(
        "maos: duas mãos pegam a mesma tarefa (gravação sem comparar e trocar)",
        "src/lifeos/maos/fila_firestore.py",
        "        if firestore_comum.trocar(_ref(snap.id), decidir):",
        '        if snap.reference.update({"estado": fila.PEGA, "pega_por": por}) or True:',
        "tests/test_maos_fila.py::test_varias_maos_ao_mesmo_tempo_so_uma_pega",
    ),
    Mutacao(
        "maos: a tarefa vencida ainda é pega",
        "src/lifeos/maos/fila_firestore.py",
        '        (s for s in consulta.stream() if _instante(s, "pegar_ate") >= agora),',
        "        (s for s in consulta.stream()),",
        "tests/test_maos_fila.py::test_tarefa_vencida_nao_e_pega",
    ),
    Mutacao(
        "maos: quem não pegou a tarefa entrega o resultado",
        "src/lifeos/maos/fila_firestore.py",
        '        if not snap.exists or snap.get("estado") != fila.PEGA or snap.get("pega_por") != por:',
        '        if not snap.exists or snap.get("estado") != fila.PEGA:',
        "tests/test_maos_fila.py::test_so_quem_pegou_entrega",
    ),
    Mutacao(
        "maos: a tarefa aceita um campo a mais (um liberar vindo da nuvem)",
        "src/lifeos/maos/fila.py",
        "    if set(dados) != set(CAMPOS):",
        "    if not set(CAMPOS) <= set(dados):",
        "tests/test_maos_fila.py::test_um_campo_a_mais_e_recusado_inclusive_liberar",
    ),
    Mutacao(
        "maos: a tarefa pede o tempo do navegador inteiro, além do turno",
        "src/lifeos/maos/pedir.py",
        "    return min(teto, restante - PROXIMO_MODELO_S - fila.PEGAR_EM.total_seconds() - FOLGA_S)",
        "    return teto",
        "tests/test_na_nuvem_maos.py::test_a_tarefa_nunca_pede_mais_do_que_o_turno_tem",
    ),
    Mutacao(
        "maos: o que não cabe no turno vira tarefa",
        "src/lifeos/maos/pedir.py",
        "    if limite < fila.LIMITE_MIN_S:",
        "    if limite < 0:",
        "tests/test_na_nuvem_maos.py::test_o_que_nao_cabe_no_turno_nem_e_criado",
    ),
    Mutacao(
        "maos: sem as mãos, o turno espera mais que os 15 s",
        "src/lifeos/maos/pedir.py",
        "        if prazo._relogio() - inicio >= fila.PEGAR_EM.total_seconds():",
        "        if prazo._relogio() - inicio >= 2 * fila.PEGAR_EM.total_seconds():",
        "tests/test_na_nuvem_maos.py::test_sem_as_maos_a_tarefa_vence_em_15_s_e_nada_roda",
    ),
    Mutacao(
        "maos: o texto da página fica no Firestore depois de lido",
        "src/lifeos/maos/pedir.py",
        "            fila_firestore.apagar(tarefa_id)\n            return atual.resultado",
        "            return atual.resultado",
        "tests/test_na_nuvem_maos.py::test_com_as_maos_o_resultado_volta_e_a_tarefa_some",
    ),
    Mutacao(
        "motor: o terminal entra na porta das mãos",
        "src/lifeos/nuvem/motor.py",
        '    "/maos/pegar": frozenset({MAOS}),',
        '    "/maos/pegar": frozenset({MAOS, CLI}),',
        "tests/test_na_nuvem_maos.py::test_o_terminal_nao_entra_nas_portas_das_maos",
    ),
    Mutacao(
        "chat_cliente: a abertura esquece o navegador das mãos",
        "src/lifeos/nuvem/chat_cliente.py",
        '    if capacidades.get("maos") is True:  # Sessão 11: o navegador do Mac, pelas mãos',
        "    if False:",
        "tests/test_chat_nuvem_cliente.py::test_a_abertura_nao_promete_o_gmail_que_nao_esta_la",
    ),
    # --- Sessão 11 (D61), C3: `viking maos` no Mac ---------------------------------------------
    Mutacao(
        "maos no Mac: roda a tarefa sem conferir o formato (um liberar passaria)",
        "src/lifeos/maos/mac.py",
        "        tarefa = fila.validar_tarefa(bruta)",
        "        tarefa = fila.Tarefa(**{c: bruta[c] for c in fila.CAMPOS})",
        "tests/test_maos_mac.py::test_tarefa_com_liberar_nao_roda",
    ),
    Mutacao(
        "maos no Mac: o código da liberação vai junto na entrega à nuvem",
        "src/lifeos/maos/mac.py",
        "    if _entregar(sessao, tarefa.id, por, texto):",
        '    if _entregar(sessao, tarefa.id, por, texto + str(getattr(proposta, "codigo", ""))):',
        "tests/test_maos_mac.py::test_o_codigo_da_liberacao_fica_neste_terminal",
    ),
    Mutacao(
        "maos no Mac: começa sem terminal",
        "src/lifeos/maos/mac.py",
        "    if not _terminal():",
        "    if False:",
        "tests/test_maos_mac.py::test_sem_terminal_nao_comeca",
    ),
    Mutacao(
        "maos no Mac: rede caída martela a nuvem sem esperar mais",
        "src/lifeos/maos/mac.py",
        "                espera = min(espera * 2, ESPERA_MAX_S)",
        "                espera = espera",
        "tests/test_maos_mac.py::test_rede_caida_espera_mais_a_cada_volta_e_nao_desiste",
    ),
    Mutacao(
        "maos no Mac: Ctrl-C no meio da tarefa não desliga",
        "src/lifeos/maos/mac.py",
        '    if resultado.error_code == "timeout_terminated":  # Ctrl-C no meio da tarefa',
        "    if False:",
        "tests/test_maos_mac.py::test_ctrl_c_no_meio_da_tarefa_entrega_e_desliga",
    ),
    Mutacao(
        "maos no Mac: continua pedindo o código depois do cancelamento",
        "src/lifeos/maos/mac.py",
        "    while confirmacao.aberta(liberacao.ACAO):",
        "    for _ in range(4):",
        "tests/test_maos_mac.py::test_tres_codigos_errados_cancelam_a_liberacao",
    ),
    Mutacao(
        "migração: executa sem o envio da nuvem ligado",
        "src/lifeos/reminders/migrar.py",
        "    if not relatorio.envio_ligado:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_executar_sem_o_envio_da_nuvem_ligado_recusa_e_nao_marca",
    ),
    Mutacao(
        "migração: o divergente de antes da cópia não para",
        "src/lifeos/reminders/migrar.py",
        "    if relatorio.divergentes:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_um_id_com_outro_conteudo_na_nuvem_nao_e_sobrescrito_e_nao_marca",
    ),
    Mutacao(
        "migração: não marca 'migrando' antes de copiar",
        "src/lifeos/reminders/migrar.py",
        "    onde.marcar(onde.MIGRANDO)\n",
        "    pass\n",
        "tests/test_lembretes_nuvem.py::test_uma_queda_no_meio_deixa_migrando_e_rodar_de_novo_termina",
    ),
    Mutacao(
        "migração: a conferência relida pulada",
        "src/lifeos/reminders/migrar.py",
        "    if relatorio.divergentes or faltam:\n",
        "    if relatorio.divergentes:\n",
        "tests/test_lembretes_nuvem.py::test_a_nuvem_que_diz_que_gravou_e_nao_gravou_e_pega_pela_conferencia",
    ),
    Mutacao(
        "migração: rodar de novo diz 'migrado' outra vez",
        "src/lifeos/reminders/migrar.py",
        "    if relatorio.migrou_agora:\n",
        "    if relatorio.estado == onde.MIGRADO:\n",
        "tests/test_lembretes_nuvem.py::test_rodar_de_novo_depois_de_migrado_nao_copia_nada",
    ),
    Mutacao(
        "migração: 'migrando' não trava as gravações",
        "src/lifeos/reminders/onde.py",
        "    if agora == MIGRANDO:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_no_meio_da_copia_nada_se_grava_e_a_lista_e_a_do_mac",
    ),
    Mutacao(
        "firestore: importar sobrescreve o que já está na nuvem",
        "src/lifeos/reminders/store_firestore.py",
        "        ref.create(documento)\n",
        "        ref.set(documento)\n",
        "tests/test_lembretes_nuvem.py::test_importar_de_novo_e_igual_e_diferente_nunca_sobrescreve",
    ),
    Mutacao(
        "lembretes na nuvem: criar no Mac migrado grava no SQLite",
        "src/lifeos/reminders/service.py",
        "    if onde.na_nuvem():  # `MigracaoEmCurso` no meio da cópia: nada se grava aqui\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_depois_de_migrado_o_mac_grava_na_nuvem_e_o_viking_db_nao_muda",
    ),
    Mutacao(
        "lembretes na nuvem: concluir no Mac migrado vai ao SQLite",
        "src/lifeos/reminders/service.py",
        "    if onde.na_nuvem():\n        from lifeos.nuvem import cliente\n\n        concluido",
        "    if False:\n        from lifeos.nuvem import cliente\n\n        concluido",
        "tests/test_lembretes_nuvem.py::test_depois_de_migrado_o_mac_grava_na_nuvem_e_o_viking_db_nao_muda",
    ),
    Mutacao(
        "lembretes na nuvem: a lista do Mac migrado é a do SQLite",
        "src/lifeos/reminders/service.py",
        "    if onde.estado() == onde.MIGRADO:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_depois_de_migrado_o_mac_grava_na_nuvem_e_o_viking_db_nao_muda",
    ),
    Mutacao(
        "lembretes na nuvem: o erro da nuvem sobe cru",
        "src/lifeos/reminders/service.py",
        '        raise Indisponivel(f"a nuvem: {exc}") from None\n',
        "        raise\n",
        "tests/test_lembretes_nuvem.py::test_nuvem_fora_vira_uma_mensagem_no_chat_no_mcp_e_na_cli",
    ),
    Mutacao(
        "lembretes na nuvem: --enviar no Mac migrado envia",
        "src/lifeos/cli.py",
        "    if args.enviar and onde.estado() is not None:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_enviar_no_mac_depois_de_migrado_recusa_e_nada_sai",
    ),
    Mutacao(
        "lembretes na nuvem: o --nuvem avisa do e-mail mesmo ligado",
        "src/lifeos/cli.py",
        "        if not envio_ligado:  # o agendador da nuvem desligado (Sessão 11)\n",
        "        if True:\n",
        "tests/test_nuvem_cliente.py::test_o_aviso_do_email_segue_o_envio_da_nuvem",
    ),
    Mutacao(
        "lembretes na nuvem: o aviso sem e-mail sempre no chat da nuvem",
        "src/lifeos/assistant/na_nuvem.py",
        '    if texto.startswith("✅") and not agendador.ligado():\n',
        '    if texto.startswith("✅"):\n',
        "tests/test_lembretes_nuvem.py::test_o_aviso_do_lembrete_na_nuvem_segue_o_envio",
    ),
    Mutacao(
        "agendador: a rodada relê os atrasados",
        "src/lifeos/reminders/agendador.py",
        "envio.enviar_vencidos(agora, listar_atrasados=False)",
        "envio.enviar_vencidos(agora, listar_atrasados=True)",
        "tests/test_lembretes_nuvem.py::test_a_rodada_nao_rele_os_atrasados",
    ),
    Mutacao(
        "agendador: a rodada que parou liga o envio",
        "src/lifeos/reminders/agendador.py",
        "    if not resultado.parou:\n",
        "    if True:\n",
        "tests/test_lembretes_nuvem.py::test_rodada_que_parou_nao_liga_o_envio",
    ),
    Mutacao(
        "agendador: ligado sem olhar a idade da última rodada",
        "src/lifeos/reminders/agendador.py",
        "    return ultima is not None and ultima >= (agora or datetime.now(UTC)) - LIGADO_POR\n",
        "    return ultima is not None\n",
        "tests/test_lembretes_nuvem.py::test_versao_diz_se_o_envio_esta_ligado",
    ),
    Mutacao(
        "motor: /versao diz o envio sempre desligado",
        "src/lifeos/nuvem/motor.py",
        '            "envio_de_lembretes": ligado,\n',
        '            "envio_de_lembretes": False,\n',
        "tests/test_lembretes_nuvem.py::test_versao_diz_se_o_envio_esta_ligado",
    ),
    Mutacao(
        "motor: /tarefas/lembretes aberta ao terminal",
        "src/lifeos/nuvem/motor.py",
        '    "/tarefas/lembretes": frozenset({AGENDADOR}),\n',
        '    "/tarefas/lembretes": frozenset({AGENDADOR, CLI}),\n',
        "tests/test_lembretes_nuvem.py::test_so_o_agendador_dispara_a_rodada",
    ),
    Mutacao(
        "motor: /lembretes/importar aberta às mãos",
        "src/lifeos/nuvem/motor.py",
        '    "/lembretes/importar": frozenset({CLI}),\n',
        '    "/lembretes/importar": frozenset({CLI, MAOS}),\n',
        "tests/test_lembretes_nuvem.py::test_so_o_terminal_do_dono_fala_com_os_lembretes",
    ),
    Mutacao(
        "motor: /lembretes/criar aceita horário sem fuso",
        "src/lifeos/nuvem/motor.py",
        "    if quando and datetime.fromisoformat(quando).tzinfo is None:\n",
        "    if False:\n",
        "tests/test_lembretes_nuvem.py::test_pedido_torto_do_mac_e_400_e_nada_muda",
    ),
    Mutacao(
        "transporte: aceita um campo a mais",
        "src/lifeos/reminders/transporte.py",
        "    if not isinstance(dados, dict) or set(dados) != set(CAMPOS):\n",
        "    if not isinstance(dados, dict) or not set(CAMPOS) <= set(dados):\n",
        "tests/test_reminders_transporte.py::test_formato_torto_e_recusado_sem_ecoar_o_conteudo",
    ),
    Mutacao(
        "transporte: aceita instante sem fuso",
        "src/lifeos/reminders/transporte.py",
        "        if momento is None or momento.tzinfo is None:\n",
        "        if momento is None:\n",
        "tests/test_reminders_transporte.py::test_formato_torto_e_recusado_sem_ecoar_o_conteudo",
    ),
    Mutacao(
        "transporte: a impressão ignora o estado do envio",
        "src/lifeos/reminders/transporte.py",
        "    canonico = json.dumps(para_dict(lembrete), sort_keys=True, ensure_ascii=False)\n",
        '    canonico = json.dumps({**para_dict(lembrete), "envio_estado": None}, sort_keys=True)\n',
        "tests/test_reminders_transporte.py::test_a_impressao_muda_com_qualquer_campo",
    ),
    Mutacao(
        "agendador: ligado sem o Gmail no motor",
        "src/lifeos/reminders/agendador.py",
        '    if config.STORE != "firestore" or not config.gmail_no_motor():\n',
        '    if config.STORE != "firestore":\n',
        "tests/test_lembretes_nuvem.py::test_sem_o_gmail_no_motor_o_envio_nunca_esta_ligado",
    ),
    Mutacao(
        "nuvem: as mãos fora das contas do dono e do deploy",
        "scripts/nuvem.py",
        "DO_DONO = (CLI, MAOS)\n",
        "DO_DONO = (CLI,)\n",
        "tests/test_nuvem_script.py::test_o_servico_nasce_fechado",
    ),
    Mutacao(
        "nuvem: contas pronta sem o dono no token das mãos",
        "scripts/nuvem.py",
        "    for nome in DO_DONO:\n        conta = _ler(",
        "    for nome in (CLI,):\n        conta = _ler(",
        "tests/test_nuvem_script.py::test_contas_sem_o_dono_no_token_das_maos_nao_esta_pronta",
    ),
    Mutacao(
        "nuvem: quem invoca aceita qualquer um a mais",
        "scripts/nuvem.py",
        "    return precisam <= quem <= podem\n",
        "    return precisam <= quem\n",
        "tests/test_nuvem_script.py::test_so_o_terminal_as_maos_e_o_agendador_invocam",
    ),
    Mutacao(
        "nuvem: a tarefa do agendador com qualquer frequência",
        "scripts/nuvem.py",
        '        "a cada minuto": tarefa.get("schedule") == "* * * * *",\n',
        '        "a cada minuto": True,\n',
        "tests/test_nuvem_script.py::test_o_agendador_so_esta_pronto_com_tudo_certo",
    ),
    Mutacao(
        "nuvem: a tarefa do agendador com qualquer audience",
        "scripts/nuvem.py",
        '        "com a audience do motor": oidc.get("audience") == url,\n',
        '        "com a audience do motor": True,\n',
        "tests/test_nuvem_script.py::test_o_agendador_so_esta_pronto_com_tudo_certo",
    ),
    Mutacao(
        "nuvem: a tarefa do agendador criada sem audience",
        "scripts/nuvem.py",
        '            f"--oidc-token-audience={url}",\n',
        '            "--oidc-token-audience=",\n',
        "tests/test_nuvem_script.py::test_a_tarefa_do_agendador_chama_so_a_rota_do_envio_com_oidc",
    ),
    Mutacao(
        "migração: o script de limpeza apaga na cópia de antes",
        "scripts/limpar_lembretes_de_teste.py",
        "    if onde.estado() is not None:\n",
        "    if False:\n",
        "tests/test_script_limpar_lembretes.py::test_depois_da_migracao_aplicar_recusa_e_nada_some",
    ),
    # 2026-10-06, o C9 da 10c no Mac: a resposta vazia do Gemini saía como "🤖 Viking: " calado.
    Mutacao(
        "turno: resposta sem texto vira um vazio calado",
        "src/lifeos/assistant/turno.py",
        '        if not (texto or "").strip():\n',
        "        if False:\n",
        "tests/test_na_nuvem.py::test_resposta_vazia_do_gemini_e_erro_com_o_motivo",
    ),
    Mutacao(
        "turno: a resposta vazia sem o motivo do Gemini",
        "src/lifeos/assistant/turno.py",
        '        motivo = f"motivo: {_nome(fim)}" if fim else "sem motivo informado"\n',
        '        motivo = "sem motivo informado"\n',
        "tests/test_na_nuvem.py::test_resposta_vazia_do_gemini_e_erro_com_o_motivo",
    ),
    Mutacao(
        "turno: o limite de tools do turno sem nome",
        "src/lifeos/assistant/turno.py",
        '        motivo = "o modelo passou do limite de chamadas de tool deste turno"\n',
        '        motivo = "sem motivo informado"\n',
        "tests/test_na_nuvem.py::test_limite_de_tools_no_turno_e_erro_e_nao_resposta_vazia",
    ),
    # --- Sessão 11c: o backup (D63) ---------------------------------------------------------
    Mutacao(
        "backup: o arquivo com um campo a mais passa",
        "src/lifeos/backup/formato.py",
        "    if set(dados) != set(CAMPOS):\n",
        "    if not set(CAMPOS) <= set(dados):\n",
        "tests/test_backup_formato.py::test_campo_a_mais_no_arquivo_e_recusado",
    ),
    Mutacao(
        "backup: a contagem do arquivo não é conferida",
        "src/lifeos/backup/formato.py",
        '    if dados["contagens"] != backup.contagens():\n',
        "    if False:\n",
        "tests/test_backup_formato.py::test_contagem_errada_e_recusada",
    ),
    Mutacao(
        "backup: a impressão dos lembretes não é conferida",
        "src/lifeos/backup/formato.py",
        '    if dados["impressoes"] != impressoes:\n',
        "    if False:\n",
        "tests/test_backup_formato.py::test_lembrete_alterado_no_arquivo_e_recusado_pela_impressao",
    ),
    Mutacao(
        "registro firestore: importar sobrescreve a ação que existe",
        "src/lifeos/registro_firestore.py",
        "        ref.create(documento)\n",
        "        ref.set(documento)\n",
        "tests/test_registro.py::test_importar_de_novo_e_igual_e_diferente_nao_sobrescreve",
    ),
    Mutacao(
        "registro sqlite: importar sobrescreve a ação que existe",
        "src/lifeos/registro_sqlite.py",
        '            f"INSERT INTO acoes ({colunas}) VALUES ({marcas}) ON CONFLICT (id) DO NOTHING",\n',
        '            f"INSERT OR REPLACE INTO acoes ({colunas}) VALUES ({marcas})",\n',
        "tests/test_registro.py::test_importar_de_novo_e_igual_e_diferente_nao_sobrescreve",
    ),
    Mutacao(
        "registro: o backup sem o corte dos 30 dias",
        "src/lifeos/registro.py",
        "    return _STORE.exportar(desde=_corte(agora))\n",
        "    return _STORE.exportar(desde=_corte(agora) - RETENCAO)\n",
        "tests/test_registro.py::test_exportar_corta_pelos_30_dias",
    ),
    Mutacao(
        "lembretes sqlite: importar sobrescreve o que existe",
        "src/lifeos/reminders/store.py",
        '            "ON CONFLICT (id) DO NOTHING",\n            valores,\n',
        '            "ON CONFLICT (id) DO UPDATE SET title = excluded.title",\n            valores,\n',
        "tests/test_reminders_contrato.py::test_importar_de_novo_e_igual_e_diferente_nunca_sobrescreve",
    ),
    Mutacao(
        "gastos: importar sobrescreve o mês que existe",
        "src/lifeos/custos.py",
        '        ref.create({"total": float(copia["total"]), "dias": dict(copia["dias"])})\n',
        '        ref.set({"total": float(copia["total"]), "dias": dict(copia["dias"])})\n',
        "tests/test_backup_formato.py::test_gasto_existente_nunca_e_sobrescrito",
    ),
    Mutacao(
        "backup: o último backup marcado antes de o Drive confirmar",
        "src/lifeos/backup/rodada.py",
        "    arquivo = drive.subir(\n",
        '    _ref().set({"ultimo": agora})\n    arquivo = drive.subir(\n',
        "tests/test_backup_rodada.py::test_drive_que_falha_nao_marca_o_backup",
    ),
    Mutacao(
        "backup: a resposta da rota leva os lembretes",
        "src/lifeos/backup/rodada.py",
        '    return {"arquivo": arquivo.nome, **dados["contagens"]}\n',
        '    return {"arquivo": arquivo.nome, **dados["contagens"], "l": dados["lembretes"]}\n',
        "tests/test_backup_rodada.py::test_o_backup_sobe_um_arquivo_que_se_le_de_volta",
    ),
    Mutacao(
        "motor: o terminal do dono dispara o backup",
        "src/lifeos/nuvem/motor.py",
        '    "/tarefas/backup": frozenset({AGENDADOR}),\n',
        '    "/tarefas/backup": frozenset({AGENDADOR, CLI}),\n',
        "tests/test_backup_rodada.py::test_so_o_agendador_dispara_o_backup",
    ),
    Mutacao(
        "drive: a pasta nasce de novo a cada backup",
        "src/lifeos/backup/drive.py",
        "        if pasta is None:\n",
        "        if True:\n",
        "tests/test_backup_drive.py::test_a_pasta_nasce_uma_vez_e_os_arquivos_se_acumulam",
    ),
    Mutacao(
        "drive: um 5xx no envio vira falhou (e não incerta)",
        "src/lifeos/backup/drive.py",
        "        raise FalhaDoDrive(_descrever(exc), incerta=escreve and not certa) from None\n",
        "        raise FalhaDoDrive(_descrever(exc), incerta=False) from None\n",
        "tests/test_backup_drive.py::test_falha_do_drive_e_incerta_so_quando_pode_ter_criado",
    ),
    Mutacao(
        "drive: o último backup sem a ordem pela criação",
        "src/lifeos/backup/drive.py",
        '            orderBy="createdTime desc",\n',
        '            orderBy="createdTime",\n',
        "tests/test_backup_drive.py::test_ultimo_e_o_mais_novo_e_nada_sem_pasta",
    ),
    Mutacao(
        "versao: o backup ligado sem o token do Drive",
        "src/lifeos/nuvem/motor.py",
        '            "backup": config.drive_no_motor(),\n',
        '            "backup": True,\n',
        "tests/test_backup_rodada.py::test_sem_o_token_do_drive_o_versao_diz_que_nao_ha_backup",
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
