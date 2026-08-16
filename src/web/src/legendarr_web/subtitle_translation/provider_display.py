"""Thin readers over the display metadata (`label`, `credential_fields`) the backend now
computes per row — built-in or plugin-supplied (ROADMAP.md 0.9.0), see
`legendarr_backend.subtitle_translation.provider_catalog`. The web layer no longer keeps
its own copy of that table, so a dynamically-loaded provider kind renders correctly
without a matching local entry.
"""


def provider_label(provider: dict) -> str:
    return provider.get("label", provider.get("kind", ""))


def provider_credential_fields(provider: dict) -> tuple[str, ...]:
    return tuple(provider.get("credential_fields", ()))
