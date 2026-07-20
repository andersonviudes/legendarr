# Subtitle Translation

Translation backends implement a single `TranslationProvider` protocol:

```python
class TranslationProvider(Protocol):
    name: str

    def translate(self, text: str, source_language: str, target_language: str) -> str: ...
```

This keeps the translation step decoupled from whichever service does the actual work —
DeepL, Google Translate, LibreTranslate, or anything else that can translate a string
between two language codes.

## Built-in providers

| Provider | Description |
| --- | --- |
| `echo` | Returns the input unchanged. Used for local development and tests. |

Provider selection isn't wired up yet — it isn't a [language profile](language-profiles.md)
field, and will land as a separate feature/use case.
