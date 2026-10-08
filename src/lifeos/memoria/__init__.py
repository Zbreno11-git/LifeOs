"""A memória de fatos do Viking (Sessão 13, D48 e D66): o que o dono conta sobre si, anotado
sozinho, só do que ele digita, e lembrado por significado no chat da nuvem.

- `regras.py`: o filtro do que pode virar fato (puro, sem rede);
- `store.py`: a coleção `memoria` do Firestore (só se acrescenta; as marcas mudam, o texto não);
- `vetores.py`: o `gemini-embedding-2` (a busca por significado);
- `extrator.py`: a chamada separada que lê só a mensagem do dono e propõe os fatos;
- `resumo.py`: o e-mail da semana.
"""
