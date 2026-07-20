# Starter list for the language-profile form's multi-select — codes are what actually
# get stored (comma-joined) on `source_languages`/`target_languages`, names are display-only.
# Not exhaustive; extend as real-world profiles need more languages.
SUPPORTED_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("es", "Spanish"),
    ("es-419", "Spanish (Latino)"),
    ("pt", "Portuguese"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("sv", "Swedish"),
    ("tr", "Turkish"),
    ("ru", "Russian"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Chinese"),
]
