"""Os documentos do Viking (Sessão 14, D68): arquivos `.md`/`.txt` que o dono manda um por um, com
um tema, e que o chat da nuvem consulta por tema e cita. Um documento é conteúdo de terceiro: o
trecho vai ao modelo no bloco de não confiável e nunca vira fato, receita nem permissão.

- `cortes.py`: o arquivo conferido e cortado em trechos (puro, sem rede);
- `store.py`: as coleções `documentos` e `trechos` do Firestore (só se acrescenta; as marcas mudam);
- `consulta.py`: a tool `consultar_documentos` do chat da nuvem (só leitura);
- `servico.py`: o que as rotas `/documentos*` do motor fazem;
- `terminal.py`: o `viking documentos` do Mac.
"""
