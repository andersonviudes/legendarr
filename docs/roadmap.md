# Roadmap

legendarr is early-stage. Planned work includes:

- **Embedded subtitle extraction** — probe video containers (via `ffprobe`/`ffmpeg`, already
  bundled in the Docker image) to discover and extract embedded subtitle tracks, not just
  external sibling files.
- **Real translation providers** — DeepL, Google Translate, and/or LibreTranslate backends
  implementing the `TranslationProvider` protocol, alongside the existing `echo` provider.
- **Language profile management UI** — create/edit/delete language profiles from the
  dashboard instead of directly in the database.
- **Published Docker image** — re-enable publishing the image to a container registry once
  the feature set stabilizes (CI currently only builds the image to validate it, without
  pushing it anywhere).

Have a feature request? Open an issue on
[GitHub](https://github.com/andersonviudes/legendarr/issues).
