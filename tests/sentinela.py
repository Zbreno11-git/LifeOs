"""Procurar um código de aprovação num texto sem falso positivo.

Um `"4821" not in texto` sobre um texto com horário, UUID ou id `time_ns` reprova por acaso: os
microssegundos de um horário saíram `…148214` e `…147391` e derrubaram o CI duas vezes em
2026-09-30, sem código nenhum vazado. Um código vazado aparece como número isolado ("confirma
4821", "código 4821."); dentro de outro número ou de um hex, não é o código.
"""

import re


def aparece(codigo: str, texto: object) -> bool:
    """O código aparece em `texto` como número isolado (sem letra ou dígito colado dos lados)?"""
    return re.search(rf"(?<![0-9A-Za-z]){re.escape(codigo)}(?![0-9A-Za-z])", str(texto)) is not None
