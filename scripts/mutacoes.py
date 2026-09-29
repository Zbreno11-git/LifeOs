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
        "src/lifeos/confirmacao.py",
        '        while (codigo := f"{secrets.randbelow(10**DIGITOS):0{DIGITOS}d}") in recentes:',
        '        while (codigo := f"{secrets.randbelow(10**DIGITOS):0{DIGITOS}d}") in ():',
        "tests/test_confirmacao.py::test_codigo_nao_se_repete_entre_acoes",
    ),
    Mutacao(
        "confirmação: proposta substituída libera o número na hora",
        "src/lifeos/confirmacao.py",
        "\"WHERE expira_em >= ? OR (estado = 'consumida' AND consumida_em >= ?)\",",
        "\"WHERE (estado = 'aberta' AND expira_em >= ?) \"\n"
        "                \"OR (estado = 'consumida' AND consumida_em >= ?)\",",
        "tests/test_confirmacao.py::test_codigo_substituido_nao_volta_enquanto_nao_vence",
    ),
    Mutacao(
        "confirmação: validade da proposta ignorada",
        "src/lifeos/confirmacao.py",
        "    expira = agora + validade",
        "    expira = agora + VALIDADE",
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
        "src/lifeos/assistant/agent.py",
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
        "src/lifeos/assistant/agent.py",
        "            aviso, nota = registro_texto.aviso_pos_erro(registro.do_turno(turno))",
        '            aviso, nota = "", ""',
        "tests/test_registro_chat.py::test_erro_depois_de_agir_diz_o_que_ja_foi_feito",
    ),
    Mutacao(
        "desfazer: a mesma ação desfeita duas vezes",
        "src/lifeos/registro.py",
        '            "WHERE id = ? AND desfeita_em IS NULL AND desfazer IS NOT NULL AND estado = ?",',
        '            "WHERE id = ? AND desfazer IS NOT NULL AND estado = ?",',
        "tests/test_registro.py::test_desfazer_duas_vezes_so_a_primeira_leva",
    ),
    Mutacao(
        "desfazer: `desfaz` alcança ações de outra sessão",
        "src/lifeos/registro.py",
        '            "AND substr(turno, 1, ?) = ? ORDER BY id DESC LIMIT 1",',
        '            "AND ? > 0 AND ? IS NOT NULL ORDER BY id DESC LIMIT 1",',
        "tests/test_registro_chat.py::test_desfaz_nao_alcanca_outra_sessao",
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
        "def concluir_lembrete(reminder_id: int) -> str:",
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
