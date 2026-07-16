# Language Profiles

A language profile is a named set of source/target languages and translation preferences.
It lets you say, for example: "for anime, translate embedded Japanese subs to `pt-BR` and
`en` using DeepL, extracting embedded tracks when no external subtitle exists".

## Fields

| Field | Description |
| --- | --- |
| `name` | Unique name for the profile. |
| `source_languages` | Language(s) legendarr should look for as the source subtitle. |
| `target_languages` | Comma-separated list of languages to translate into. |
| `translation_provider` | Which [translation provider](subtitle-translation.md) to use for this profile. Defaults to `echo`. |
| `extract_embedded_subtitles` | Whether to extract embedded subtitle tracks when no external subtitle is found. Defaults to `true`. |

## Managing profiles

Profiles are viewable at `/settings/` in the web dashboard. They're stored in the
`LanguageProfile` table in the shared SQLite database (see
`modules/backend/src/legendarr_backend/language_profiles/models.py`).
