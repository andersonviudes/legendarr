from pydantic import BaseModel, Field


class LanguageProfileInput(BaseModel):
    name: str = Field(min_length=1)
    source_languages: str = Field(min_length=1)
    target_languages: str = Field(min_length=1)
    auto_translate: bool = True
    extract_embedded_subtitles: bool = True
    ocr_embedded_subtitles: bool = False
    speech_to_text_fallback: bool = False
    forced: bool = False
    hearing_impaired: bool = False
    is_default: bool = False
    release_name_must_contain: str = ""
    release_name_must_not_contain: str = ""
    movie_match_score: int = Field(default=40, ge=0, le=100)
    series_match_score: int = Field(default=40, ge=0, le=100)
