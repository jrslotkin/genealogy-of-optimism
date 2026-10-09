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
- Every released episode also gets its own page at `docs/ep/N/` with a share card
  (`docs/ep/N/og.jpg`) built from its pull quote.

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

## Analytics

The page reports to PostHog (US cloud) when `POSTHOG_KEY` in `build/build_site.py` is set.
The key is public by design: it can send events, not read them.

- **Automatic:** pageviews, time on page, location (city-level, from IP), device, referrer and
  UTM tags, every click, heatmaps, rage and dead clicks, web vitals, JavaScript errors, and
  session replays when replay is on in the PostHog project.
- **Custom events:**
  - Following: `follow_click` (by app), `follow_app_not_opened`, `follow_app_opened_late` (the app opened
    after the browser asked first), `feed_copied`,
    `rss_link_click`, `other_apps_click`
  - Listening: `episode_play` (with trigger: play button, pull quote, chapter, transcript),
    `episode_listen` (seconds heard, share of episode heard), `episode_progress` (25/50/75/90%),
    `episode_finished`, `playback_speed_change`, `audio_error`
  - Navigation: `pull_quote_click`, `chapter_click`, `transcript_click`, `download`,
    `syllabus_open`, `outbound_click`, `episode_section_open`, `earlier_episode_open`,
    `act_open`, `act_listen_click`, `book_link_open`, `text_copied`, `section_viewed`
  - Engagement: `page_engagement` (engaged seconds, deepest scroll)
- Every book on the page has an anchor (`#book-N`) that opens its act and marks the book. The
  syllabus PDF links each title there with `?utm_source=pdf`, so PDF readers show up as their own source.
- The QR code carries `?utm_source=qr`. The page removes UTM tags from the address bar after
  recording them.
- Open the site with `?notrack` to stop counting that browser, and `?track` to undo it. Local
  previews aren't counted unless opened with `?track`. PostHog drops automated browsers.
