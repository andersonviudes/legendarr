from pydantic import BaseModel, Field


class LanguageProfileInput(BaseModel):
    name: str = Field(min_length=1)
    source_languages: str = Field(min_length=1)
    target_languages: str = Field(min_length=1)
    translation_provider: str = "echo"
    extract_embedded_subtitles: bool = True
    forced: bool = False
    hearing_impaired: bool = False
    is_default: bool = False
