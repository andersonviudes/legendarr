from sqlmodel import Field, SQLModel


class LanguageProfile(SQLModel, table=True):
    """A named set of target languages and translation preferences.

    Lets a user say, e.g., "for anime, translate embedded Japanese subs to
    pt-BR and en, extracting embedded tracks when no external subtitle exists".
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    source_languages: str
    target_languages: str
    extract_embedded_subtitles: bool = Field(default=True)
    forced: bool = Field(default=False)
    hearing_impaired: bool = Field(default=False)
    is_default: bool = Field(default=False)

    @property
    def source_language_list(self) -> list[str]:
        """`source_languages` split into codes, comma order preserved (that order is the
        priority a translation source is picked in — see `subtitle_translation`)."""
        return [
            language.strip() for language in self.source_languages.split(",") if language.strip()
        ]

    @property
    def target_language_list(self) -> list[str]:
        """`target_languages` split into codes, comma order preserved."""
        return [
            language.strip() for language in self.target_languages.split(",") if language.strip()
        ]
