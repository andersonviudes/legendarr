import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.http_client.rate_limit import retry_on_rate_limit
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider

logger = logging.getLogger(__name__)

# Google Cloud Translation API v2 rejects a request with more than 128 `q` text
# segments ("Too many text segments") — a real subtitle routinely has more lines than
# that, so the batch has to be split into chunks of at most this size.
MAX_TEXT_SEGMENTS_PER_REQUEST = 128

GOOGLE_FREE_BASE_URL = "https://translate.googleapis.com"
# The keyless endpoint is meant for a browser: the default httpx user-agent gets throttled
# far harder than a browser one. Bazarr vendors a patched `deep_translator` for exactly
# this reason, which is also why we don't depend on that library.
GOOGLE_FREE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
# The keyless endpoint takes one line per request, so a feature-length subtitle is well
# over a thousand of them and they have to overlap to finish in reasonable time. Kept
# below Bazarr's 10 because `scheduling.provider_concurrency` already lets
# `PROVIDER_MAX_CONCURRENCY` media files translate at once — this is really up to 18
# requests in flight against a host that rate-limits aggressively.
GOOGLE_FREE_MAX_WORKERS = 6
# Whole-subtitle ceiling: whatever hasn't come back by then is abandoned and falls under
# the failure ratio below, so a wedged request can't hold a bulk-queue worker forever.
GOOGLE_FREE_TIMEOUT_SECONDS = 900.0
# How much of a subtitle may fail before the whole translation is treated as failed.
# Under it, the failed lines keep their source text and the job still produces a usable
# file (Bazarr's behavior); over it, raising is better than silently writing a mostly
# untranslated subtitle — the circuit breaker records it and `_translate_with_fallback`
# moves on to the next provider in the chain.
MAX_FAILED_LINE_RATIO = 0.1


class GoogleCloudTranslationProvider:
    """Google Cloud Translation (v2) `translate()` backend — the paid API, used when the
    config carries an API Key. See `GoogleFreeTranslationProvider` for the keyless one.
    """

    name = "google"

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient("Google Translate", "https://translation.googleapis.com")
        try:
            translated_texts = []
            for start in range(0, len(texts), MAX_TEXT_SEGMENTS_PER_REQUEST):
                chunk = texts[start : start + MAX_TEXT_SEGMENTS_PER_REQUEST]
                response = client.post_json(
                    f"/language/translate/v2?key={self._api_key}",
                    {
                        "q": chunk,
                        "source": source_language,
                        "target": target_language,
                        "format": "text",
                    },
                )
                translated_texts.extend(
                    translation["translatedText"]
                    for translation in response["data"]["translations"]
                )
        finally:
            client.close()
        return translated_texts


class GoogleFreeTranslationProvider:
    """Google Translate's public keyless endpoint (`translate_a/single`), the same one
    Bazarr's default translator uses — the only backend here that needs no account at all.

    It takes a single string per request rather than a batch, so a subtitle goes out as
    one request per line, overlapped across `GOOGLE_FREE_MAX_WORKERS` threads and retried
    on 429. This is an undocumented endpoint Google can change without notice; the
    per-line failure tolerance below exists because it *will* refuse some requests.
    """

    name = "google"

    def __init__(self, config: TranslationProviderConfig) -> None:
        # Takes the config only to satisfy `provider_chain._ProviderFactory`; this backend
        # is keyless by definition, so there's nothing on it to read.
        pass

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient(
            "Google Translate",
            GOOGLE_FREE_BASE_URL,
            headers={"User-Agent": GOOGLE_FREE_USER_AGENT},
        )
        try:
            translated = _translate_each(
                texts,
                lambda text: _translate_one(client, text, source_language, target_language),
            )
        finally:
            client.close()
        return _replace_failures_with_source(texts, translated)


def build_google_provider(config: TranslationProviderConfig) -> TranslationProvider:
    """Pick the Google backend this config asks for: a stored API Key means the paid Cloud
    Translation API, a blank one means the keyless public endpoint.

    Both report `name = "google"`, so circuit-breaker state, `TranslationAttempt.provider`
    and the System > Providers page don't split in two when a user adds or removes a key.
    """
    if config.api_key:
        return GoogleCloudTranslationProvider(config)
    return GoogleFreeTranslationProvider(config)


def _translate_one(
    client: ProviderHttpClient, text: str, source_language: str, target_language: str
) -> str:
    if not text.strip():
        return text
    query = urlencode(
        {
            "client": "gtx",
            "sl": source_language,
            "tl": target_language,
            "dt": "t",
            "q": text,
        }
    )
    payload = retry_on_rate_limit(
        lambda: client.get_json(f"/translate_a/single?{query}"),
        description="Google Translate",
    )
    return _join_segments(payload)


def _join_segments(payload: Any) -> str:
    """`translate_a/single` answers with a nested array whose first element holds one
    `[translated, original, ...]` entry per sentence Google split the input into —
    rejoining them is what reconstitutes a multi-sentence subtitle line."""
    segments = payload[0] if payload else None
    if not segments:
        return ""
    return "".join(segment[0] for segment in segments if segment and segment[0])


def _translate_each(texts: list[str], translate_one: Callable[[str], str]) -> list[str | None]:
    """Run `translate_one` over every entry of `texts` concurrently, returning results in
    input order with `None` wherever a line failed or never came back.

    A `ThreadPoolExecutor` is deliberately not used, for the reason
    `subtitle_acquisition.provider_search._search_all` documents: its `__exit__` is a
    `shutdown(wait=True)`, so one request wedged on something no HTTP timeout covers would
    hold this worker forever, and its non-daemon threads would block interpreter shutdown.
    Unlike `_search_all` this can't spawn a thread per item — there are as many items as
    subtitle lines — so a fixed pool of daemon threads drains a shared queue instead,
    joined against one shared deadline.
    """
    results: list[str | None] = [None] * len(texts)
    pending: queue.Queue[int] = queue.Queue()
    for index in range(len(texts)):
        pending.put(index)

    def _worker() -> None:
        while True:
            try:
                index = pending.get_nowait()
            except queue.Empty:
                return
            try:
                results[index] = translate_one(texts[index])
            except Exception:
                logger.debug("Google Translate failed for subtitle line %d", index, exc_info=True)

    threads = [
        threading.Thread(target=_worker, daemon=True)
        for _ in range(min(GOOGLE_FREE_MAX_WORKERS, len(texts)))
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + GOOGLE_FREE_TIMEOUT_SECONDS
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    return results


def _replace_failures_with_source(texts: list[str], translated: list[str | None]) -> list[str]:
    failed = [index for index, text in enumerate(translated) if text is None]
    if len(failed) > len(texts) * MAX_FAILED_LINE_RATIO:
        raise ProviderClientError(
            f"Google Translate failed for {len(failed)} of {len(texts)} subtitle lines"
        )
    if failed:
        logger.warning(
            "Google Translate failed for %d of %d subtitle lines, keeping their source text",
            len(failed),
            len(texts),
        )
    return [texts[index] if text is None else text for index, text in enumerate(translated)]
