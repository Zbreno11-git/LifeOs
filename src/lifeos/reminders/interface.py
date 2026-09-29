"""A interface do store de lembretes (Sessão 9, D56): o que o SQLite de hoje e o Firestore da
Sessão 10 têm de fazer igual, e nada além disso.

Operações pequenas e explícitas: buscar por id, listar os abertos, concluir, os vencidos numa
janela e a reserva de envio. Nada de consulta solta fora do store. `tests/test_reminders_contrato.py`
roda o mesmo contrato em toda implementação; o `mypy` confere que o módulo `store` satisfaz este
`Protocol` (`reminders/service.py`).

Regras que valem para todas:
- **id UUID gerado no cliente:** repetir o `add` com o mesmo id devolve o que existe (retentativa
  sem duplicar); o Firestore não tem contador;
- **só instantes:** `datetime` sem fuso é recusado (`ValueError`); quem recebe o texto do dono
  converte no fuso dele, na borda (`service.py`). Tudo volta em UTC;
- **concluir é idempotente:** concluir de novo não muda a hora;
- **reserva de envio com prazo:** `reservar_envio` só uma execução ganha (até `ate`, ou até
  `marcar_envio`/`soltar_envio`); vencido o prazo, outra pode pegar (quem reservou morreu no
  meio). O Scheduler da nuvem entrega "at least once": a reserva é o que faz um envio só.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from lifeos.reminders.models import Reminder

ENVIADO, INCERTO = "enviado", "incerto"


class Lembretes(Protocol):
    def add(
        self,
        title: str,
        body: str = "",
        type: str = "reminder",
        tags: list[str] | None = None,
        due_at: datetime | None = None,
        source: str = "manual",
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> Reminder: ...

    def get(self, reminder_id: str) -> Reminder | None: ...

    def list_open(self, type: str | None = None) -> list[Reminder]: ...

    def complete(self, reminder_id: str) -> Reminder | None: ...

    def vencidos(self, desde: datetime, ate: datetime) -> list[Reminder]:
        """Abertos, com prazo em `[desde, ate]`, sem envio marcado; pelo prazo."""
        ...

    def atrasados(self, antes_de: datetime) -> list[Reminder]:
        """Abertos, com prazo antes de `antes_de`, sem envio marcado; pelo prazo."""
        ...

    def reservar_envio(self, reminder_id: str, *, por: str, ate: datetime, agora: datetime) -> bool:
        """Só um ganha: aberto, sem envio marcado e sem reserva viva em `agora`."""
        ...

    def marcar_envio(self, reminder_id: str, *, por: str, estado: str, agora: datetime) -> bool:
        """Grava o envio (`ENVIADO` ou `INCERTO`) e solta a reserva, só se a reserva é de `por`."""
        ...

    def soltar_envio(self, reminder_id: str, *, por: str) -> None:
        """Devolve a reserva de `por` (falha definitiva, limite): a próxima execução tenta."""
        ...
