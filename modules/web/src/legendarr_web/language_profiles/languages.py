# Language-profile form's multi-select — codes are what actually get stored (comma-joined)
# on `source_languages`/`target_languages`, names are display-only. Curated to the ~25
# languages that ship by default as subtitle/audio options on major video streaming
# platforms (Netflix, Prime Video, Disney+), not an exhaustive ISO list.
SUPPORTED_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("es", "Spanish"),
    ("es-419", "Spanish (Latin America)"),
    ("pt", "Portuguese"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("sv", "Swedish"),
    ("no", "Norwegian"),
    ("da", "Danish"),
    ("fi", "Finnish"),
    ("tr", "Turkish"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("ar", "Arabic"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Chinese (Simplified)"),
    ("th", "Thai"),
    ("vi", "Vietnamese"),
]
