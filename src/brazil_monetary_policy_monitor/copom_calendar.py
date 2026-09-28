"""Documentary Copom meeting/RPM calendar entries from official BCB publications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ScheduledPolicyEvent:
    key: str
    event_type: str
    title: str
    occurred_on: date
    source_url: str
    source_published_on: date | None = None
    meeting_number: int | None = None
    status: str = "scheduled"
    metadata: dict[str, object] | None = None


# Future 2026 dates visible in the BCB Copom calendar when this registry was established.
# Past meetings are taken from the machine-readable document API instead.
COPOM_SCHEDULE: tuple[ScheduledPolicyEvent, ...] = (
    ScheduledPolicyEvent(
        key="copom-meeting-282",
        event_type="copom_meeting",
        title="282ª Reunião do Copom — decisão",
        occurred_on=date(2026, 11, 4),
        meeting_number=282,
        source_url="https://www.bcb.gov.br/controleinflacao/copom",
        status="scheduled",
        metadata={"meeting_start": "2026-11-03", "meeting_end": "2026-11-04"},
    ),
    ScheduledPolicyEvent(
        key="copom-meeting-283",
        event_type="copom_meeting",
        title="283ª Reunião do Copom — decisão",
        occurred_on=date(2026, 12, 9),
        meeting_number=283,
        source_url="https://www.bcb.gov.br/controleinflacao/copom",
        status="scheduled",
        metadata={"meeting_start": "2026-12-08", "meeting_end": "2026-12-09"},
    ),
    # 2027 calendar was formally published by Comunicado 45.452 on 2026-06-23.
    *tuple(
        ScheduledPolicyEvent(
            key=f"copom-calendar-2027-{index}",
            event_type="copom_meeting",
            title=f"Reunião ordinária do Copom — {end.strftime('%d/%m/%Y')}",
            occurred_on=end,
            source_url="https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45452&tipo=Comunicado",
            source_published_on=date(2026, 6, 23),
            status="scheduled",
            metadata={"meeting_start": start.isoformat(), "meeting_end": end.isoformat(), "calendar_year": 2027},
        )
        for index, (start, end) in enumerate(
            (
                (date(2027, 1, 26), date(2027, 1, 27)),
                (date(2027, 3, 16), date(2027, 3, 17)),
                (date(2027, 4, 27), date(2027, 4, 28)),
                (date(2027, 6, 15), date(2027, 6, 16)),
                (date(2027, 8, 3), date(2027, 8, 4)),
                (date(2027, 9, 21), date(2027, 9, 22)),
                (date(2027, 10, 26), date(2027, 10, 27)),
                (date(2027, 12, 7), date(2027, 12, 8)),
            ),
            start=1,
        )
    ),
)
