# A Genealogy of Technological Optimism

The listener site for the podcast: one hundred books in ten acts, ten minutes each.
Created and hosted by Jon Slotkin.

**Live site:** https://jrslotkin.github.io/genealogy-of-optimism/

## How it is built

- `docs/` is the published site. GitHub Pages serves it from the `main` branch.
- `build/build_site.py` regenerates `docs/` from:
  - `build/content.py`: the 100 books, their acts and notes
  - `build/episodes.json`: one entry per released episode (number, duration in seconds,
    summary, chapters, transcript file, sources)
  - `build/assets/`: cover art, syllabus PDF and fonts
- Episode audio is stored once, in `docs/audio/ep001.mp3`, `ep002.mp3`, and so on.

## Adding an episode

1. Put the MP3 in `build/episodes/` (any name) and the transcript as a `.txt` file
   in the same folder.
2. Add an entry to `build/episodes.json` with `audio_file` and `transcript_file` set to those
   names.
3. Run `python3 build/build_site.py`. It needs Python with Pillow, segno and Playwright.
   The MP3 is moved into `docs/audio/`.
4. Commit and push.

The page also reads the RSS feed in the visitor's browser when the feed host allows it,
so new episodes can appear before the site is rebuilt.
