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
