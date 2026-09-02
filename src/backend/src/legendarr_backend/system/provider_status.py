from collections.abc import Iterable
from datetime import datetime

from sqlmodel import Session, select

from legendarr_backend.scheduling.circuit_breaker import BreakerCategory, get_state
from legendarr_backend.subtitle_acquisition.models import (
    SUBTITLE_PROVIDER_KINDS,
    AcquisitionAttempt,
)
from legendarr_backend.subtitle_translation.models import (
    TRANSLATION_PROVIDER_KINDS,
    TranslationAttempt,
)
from legendarr_backend.subtitle_translation.plugins import plugin_kinds
from legendarr_backend.system.schemas import ProviderHealthRead


def list_provider_health(session: Session) -> list[ProviderHealthRead]:
    """Per-provider health for the System > Providers status page: circuit-breaker
    state (in-memory, resets on restart) plus last known success, read from the
    `TranslationAttempt`/`AcquisitionAttempt` audit trails — mirrors
    `statistics.compute_statistics`'s idiom of a Python-side reduction over
    `session.exec(select(Model))` rather than a SQL `GROUP BY` (no precedent for one
    in this backend). Enumerates every known provider kind, not just the ones with a
    config row, so a not-yet-configured provider still appears with empty health.
    """
    last_translation_success = _last_success_by_provider(
        (attempt.provider, attempt.translated_at)
        for attempt in session.exec(select(TranslationAttempt))
    )
    last_acquisition_success = _last_success_by_provider(
        (attempt.provider, attempt.attempted_at)
        for attempt in session.exec(select(AcquisitionAttempt))
    )
    entries = [
        _entry(BreakerCategory.TRANSLATION, kind, last_translation_success)
        for kind in (*TRANSLATION_PROVIDER_KINDS, *plugin_kinds())
    ]
    entries += [
        _entry(BreakerCategory.ACQUISITION, kind, last_acquisition_success)
        for kind in SUBTITLE_PROVIDER_KINDS
    ]
    return entries


def _last_success_by_provider(records: Iterable[tuple[str, datetime]]) -> dict[str, datetime]:
    last_success: dict[str, datetime] = {}
    for provider, occurred_at in records:
        if provider not in last_success or occurred_at > last_success[provider]:
            last_success[provider] = occurred_at
    return last_success


def _entry(
    category: BreakerCategory, kind: str, last_success_by_provider: dict[str, datetime]
) -> ProviderHealthRead:
    snapshot = get_state(category, kind)
    return ProviderHealthRead(
        kind=kind,
        category=category.value,
        circuit_open=snapshot.is_open,
        consecutive_failures=snapshot.consecutive_failures,
        opened_at=snapshot.opened_at,
        last_success_at=last_success_by_provider.get(kind),
    )
