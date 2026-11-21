# Mini-auditoria — 2026-11-21 (18:23–18:35Z, `date -u`)

Commit: `babe586` (= o GitHub, `git rev-list --left-right --count master...origin/master` → `0 0`).
No ar: o motor e o `financas` em `56f0807` (`python scripts/nuvem.py deploy`, 18:24Z), 0 commits
desde nos caminhos da imagem. Janelas evitadas: o backup (09:00Z); o envio de lembretes roda a
cada minuto, e só se leu. Só leitura: nada mudou na nuvem nem no repositório durante a medição.

| # | área | achado | sev. | evidência | próxima ação | dono |
|---|---|---|---|---|---|---|
| 1 | deps | 20 vulnerabilidades em 8 pacotes da imagem (authlib, certifi, dnspython, fastmcp, joserfc, oauthlib, opentelemetry-api, pyasn1), todas com correção; 21 alertas do Dependabot abertos desde 2026-10-29. A `certifi` (crítica: raízes de uma autoridade comprometida) está no TLS de saída do motor; authlib e fastmcp estão em código que o motor não importa (grep, não execução) | ALTO pela régua; risco prático baixo | pip-audit com a invocação do CI (18:24Z); `gh api …/dependabot/alerts` (18:25Z) | `uv lock --upgrade` (D45) e deploy, na 14b | agente |
| 2 | testes | `test_contaveis_so_da_operacao_e_sem_as_que_falharam` falha nas duas variantes: o `T0` fixo (2026-09-27) saiu da janela de 30 dias de `registro._corte` | MÉDIO | `python -m pytest -q` → `2 failed, 3198 passed` (18:30Z) | o teste no relógio real e uma varredura de outras datas fixas, na 14b | agente |
| 3 | processo | o pip-audit só roda em push; sem push desde 2026-10-09, foram 43 dias sem conferência | MÉDIO | `.github/workflows/testes.yml` sem `schedule` | o CI semanal, na 14b | agente |
| 4 | alertas | nenhuma política do Cloud Monitoring: o envio de lembretes ou o backup parar não avisa ninguém (só o `deploy` manual pega); as rotas agendadas não logam nada no sucesso | MÉDIO | `gcloud monitoring policies list` → vazio (18:25Z) | o passo `alertas` (e-mail do dono), na 14b | dono (o canal), agente |
| 5 | config | `VIKING_TIMEZONE=America/Los_Angeles` no motor; o dono já mora em SP. O `deploy` confere só o nome da variável, e trocar o `.env` sem commit não seria aplicado | MÉDIO | `run services describe motor` (18:26Z) | o fuso de SP e a prova do valor, na 14b | dono (o fuso), agente |
| 6 | IAM | `roles/editor` na conta padrão do Compute (padrão do GCP; nenhum serviço do Viking roda com ela; não documentado) | BAIXO | `projects get-iam-policy` (18:25Z) | o passo `editor`, na 14b | dono (o ok), agente |

**Conferido sem achado:**
- `python scripts/nuvem.py`: 13 ✅.
- `deploy`: 34 ✅, entre elas os segredos só como volume, as recusas sem token e com o token errado, a imagem certa e as finanças isoladas.
- Nenhuma chave baixada em nenhuma das 6 contas de serviço.
- Agendadores: `viking-lembretes` na última tentativa às 18:25Z; `viking-backup` às 09:00Z de hoje, com o arquivo novo mais recente de 2026-11-12, porque só sobe quando o conteúdo muda.
- Resumo semanal: `estado/resumo-2026-W42` a `W47`, um por segunda.
- Logs de 30 dias: 0 com `severity>=ERROR`. Os 9 avisos de hoje são as recusas das próprias provas.
- Gasto com o Gemini: US$ 0,092 em outubro (06 a 09/10) e nenhum documento de novembro, ou seja, sem uso.
- Dado pessoal numa amostra de 7 dias (49 entradas): 0 e-mails e 0 CPFs. Os 10 "telefones" eram identificadores em hexadecimal.
- `uv lock --check`, ruff, format, mypy e gitleaks (224 commits) limpos.
- Actions fixadas por SHA, e o CI do HEAD em `success`.

**Gatilhos:**
- Teto do Gemini (D59: o gasto real passar do teto): não atingido (US$ 0,09 contra US$ 10 por mês).
- "O dono se mudar de novo" (D58): **atingido**, e vira o achado 5.
- Cota grátis do Firestore: não atingida, porque o uso é de um único usuário. Não medi a contagem exata.

**Não verificado:**
- A fatura do GCP item por item: não há exportação de cobrança, só o orçamento com alertas.
- Os locks dos clones `jev-ultrafast` e `windows-mcp`.
- Se os e-mails do resumo semanal chegaram: o estado diz que rodaram, mas a caixa é do dono.
- Se o motor executa, de fato, o código vulnerável de `pyasn1` e `dnspython`.

**Escalar para a `auditoria-geral`?** Não. Nenhuma classe nova de defeito apareceu: os achados 1 e 3 são a mesma falta de rotina, e os demais têm régua no projeto ou viram uma régua nesta sessão.
