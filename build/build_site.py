"""Build the listener site for A Genealogy of Technological Optimism.

  python3 build/build_site.py      # rebuilds docs/, which GitHub Pages publishes

Episode data lives in build/episodes.json. Transcripts go in build/episodes/. Episode audio
lives once, in docs/audio/ (named ep001.mp3, ep002.mp3, ...); a new file dropped in
build/episodes/ is moved there on the next build.
"""
import html
import json
import os
import pathlib
import re
import shutil
import sys
import zipfile
from urllib.parse import quote

import segno
from PIL import Image

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from content import ACTS  # noqa: E402

TITLE = "A Genealogy of Technological Optimism"
HOST = "Jon Slotkin"
HOST_URL = "https://x.com/slotkinjr"
FEED_URL = os.environ.get(
    "FEED_URL",
    "http://muse.ai/podcasts/feed/1259445163926232/56841503-f373-44e6-99b5-326cfad9be97").strip()
FEED_FETCH = os.environ.get("FEED_FETCH") or re.sub(r"^http://", "https://", FEED_URL)
SITE_URL = os.environ.get("SITE_URL", "https://jrslotkin.github.io/genealogy-of-optimism").strip().rstrip("/")
ASSETS = ROOT / "assets"
COVER_SRC = pathlib.Path(os.environ.get("COVER", ASSETS / "cover.webp"))
PDF_SRC = ASSETS / "syllabus.pdf"
EP_DIR = pathlib.Path(os.environ.get("EP_DIR", ROOT / "episodes"))
EP_JSON = pathlib.Path(os.environ.get("EPISODES_JSON", ROOT / "episodes.json"))
OUT = pathlib.Path(os.environ.get("SITE_OUT", ROOT.parent / "docs"))
MONTH = "October 2026"

DESCRIPTION = ("One hundred books in ten acts, ten minutes each: how the idea of technological "
               "progress was built, and the strongest arguments against it.")
NOTE = [
    "An intellectual genealogy of technological optimism in 100 books, ordered as an argument "
    "in ten acts. It starts with the theology the idea of progress grew out of and the psychology "
    "of the people who act on it. It then moves through how knowledge grows, how markets and "
    "institutions turn knowledge into growth, how innovation is built and financed, and the "
    "attempt to engineer away every remaining constraint.",
    "About three quarters of the books make the case. The other quarter are the strongest "
    "arguments against it. Each critic sits next to the claim it attacks, and critiques of "
    "technology as such are held for the end.",
]


def e(s):
    return html.escape(str(s), quote=True)


def main_title(t):
    return t.split(": ", 1)[0]


def to_seconds(v):
    if isinstance(v, (int, float)):
        return int(v)
    total = 0
    for p in str(v).strip().split(":"):
        total = total * 60 + int(p)
    return total


def clock(sec):
    sec = int(round(sec or 0))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def minutes(sec):
    m, s = divmod(int(sec), 60)
    return f"{m} min {s} sec" if s else f"{m} min"


# ------------------------------------------------------------------ data
BOOKS = {}
for roman, act_name, _d, items in ACTS:
    for num, title, year, author, note in items:
        BOOKS[num] = dict(n=num, title=main_title(title), year=year, author=author,
                          note=note, roman=roman, act=act_name)

EPISODES = sorted(json.loads(EP_JSON.read_text()), key=lambda x: -x["num"])
RELEASED = {ep["num"] for ep in EPISODES}

bare = re.sub(r"^https?://", "", FEED_URL)
APPS = {
    "apple": ("Apple Podcasts", "podcast://" + bare),
    "overcast": ("Overcast", "overcast://x-callback-url/add?url=" + quote(FEED_URL, safe="")),
    "pocketcasts": ("Pocket Casts", "pktc://subscribe/" + bare),
    "castro": ("Castro", "castro://subscribe/" + bare),
    "antennapod": ("AntennaPod", "https://antennapod.org/deeplink/subscribe?url="
                   + quote(FEED_URL, safe="") + "&title=" + quote(TITLE, safe="")),
}


def app_link(key, primary=False):
    name, href = APPS[key]
    ext = ' target="_blank" rel="noopener"' if href.startswith("https://") else ""
    cls = "pill pill-ink" if primary else "pill"
    label = f"Follow in {name}" if primary else name
    return f'<a class="{cls}" data-app="{key}" data-name="{e(name)}" href="{e(href)}"{ext}>{e(label)}</a>'


# ------------------------------------------------------------------ pieces
ICONS = ('<svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 5.8v12.4L18.6 12z" fill="currentColor"/></svg>'
         '<svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 5.5h3v13h-3zM13.5 5.5h3v13h-3z" fill="currentColor"/></svg>')


def player_html(src, dur):
    return f"""
          <div class="player" data-src="{e(src)}" data-dur="{dur}">
            <audio preload="none"></audio>
            <button class="play" type="button" aria-label="Play">{ICONS}</button>
            <div class="track">
              <input class="seek" type="range" min="0" max="{dur or 1}" step="1" value="0" aria-label="Position">
              <div class="times"><span class="cur">0:00</span><span class="rem">&minus;{clock(dur)}</span></div>
            </div>
            <div class="tools">
              <button class="tool back" type="button" aria-label="Back 15 seconds">&minus;15</button>
              <button class="tool fwd" type="button" aria-label="Forward 30 seconds">+30</button>
              <button class="tool rate" type="button" aria-label="Playback speed">1&times;</button>
            </div>
          </div>"""


def episode_audio(ep):
    b = BOOKS[ep["num"]]
    nice = f"{ep['num']:02d} {b['title']}.mp3"
    dest = OUT / "audio" / f"ep{ep['num']:03d}.mp3"
    if ep.get("audio_file") and (EP_DIR / ep["audio_file"]).exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(EP_DIR / ep["audio_file"]), dest)
    if dest.exists():
        return f"audio/{dest.name}", nice, True, dest.stat().st_size / 1e6
    if ep.get("audio_url"):
        return ep["audio_url"], nice, False, None
    return "", nice, False, None


def transcript_html(ep):
    f = ep.get("transcript_file")
    if not f or not (EP_DIR / f).exists():
        return ""
    paras = []
    for block in re.split(r"\n\s*\n", (EP_DIR / f).read_text(encoding="utf-8").strip()):
        block = " ".join(line.strip() for line in block.splitlines())
        m = re.match(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–]?\s*(.*)$", block)
        if m:
            paras.append(f'<p><a class="ts" href="#" data-t="{to_seconds(m.group(1))}">{m.group(1)}</a>{e(m.group(2))}</p>')
        else:
            paras.append(f"<p>{e(block)}</p>")
    return f'<details class="fold"><summary>Transcript</summary><div class="transcript">{"".join(paras)}</div></details>'


def episode_html(ep, latest):
    b = BOOKS[ep["num"]]
    dur = to_seconds(ep.get("duration") or 0)
    src, nice, local, size = episode_audio(ep)
    meta = f'{e(b["author"])}<span class="dot">{b["year"]}</span>' + (f'<span class="dot">{minutes(dur)}</span>' if dur else "")
    dl = ""
    if src:
        size_txt = f'<span class="size">MP3, {size:.1f} MB</span>' if size else ""
        note = "" if local else '<span class="size">On iPhone, touch and hold, then tap Download Linked File.</span>'
        dl = f'<p class="dl"><a href="{e(src)}" download="{e(nice)}">Download episode</a>{size_txt}{note}</p>'
    chapters = ""
    if ep.get("chapters"):
        rows = "".join(f'<li><a href="#" data-t="{to_seconds(t)}"><span class="ct">{clock(to_seconds(t))}</span>'
                       f'<span class="cn">{e(name)}</span></a></li>' for t, name in ep["chapters"])
        chapters = f'<details class="fold"><summary>Chapters</summary><ol class="chapters">{rows}</ol></details>'
    sources = ""
    if ep.get("sources"):
        def src_li(s):
            if isinstance(s, dict) and s.get("url"):
                return f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["text"])}</a></li>'
            return f'<li>{e(s if isinstance(s, str) else s.get("text", ""))}</li>'
        sources = f'<details class="fold"><summary>Sources</summary><ul class="sources">{"".join(src_li(s) for s in ep["sources"])}</ul></details>'
    folds = chapters + transcript_html(ep) + sources
    return f"""
        <article class="ep row{' is-latest' if latest else ''}" id="ep-{ep['num']}" data-n="{ep['num']}" data-act="{b['roman']}" data-title="{e(b['title'])}">
          <div class="gut num">{ep['num']}</div>
          <div class="body">
            <p class="kicker"><span class="num-inline">{ep['num']}</span><span class="latest">Latest</span><span class="kact">Act {b['roman']}</span></p>
            <h3>{e(b['title'])}</h3>
            <p class="meta">{meta}</p>
            {player_html(src, dur) if src else ''}
            <p class="summary">{e(ep.get('summary') or b['note'])}</p>
            {dl}
            {f'<div class="folds">{folds}</div>' if folds else ''}
          </div>
        </article>"""


def act_html(roman, name, entries):
    a, z = entries[0][0], entries[-1][0]
    ticks = "".join(f'<i data-n="{b[0]}"{" class=on" if b[0] in RELEASED else ""}></i>' for b in entries)
    books = []
    for num, title, year, author, _note in entries:
        out = num in RELEASED
        listen = f'<a class="listen" href="#ep-{num}">Listen</a>' if out else ""
        books.append(f'<li data-n="{num}"{" class=out" if out else ""}><span class="bn">{num}</span>'
                     f'<span class="bt">{e(main_title(title))}<span class="ba">{e(author)}<span class="dot">{year}</span></span></span>{listen}</li>')
    return f"""
        <details class="act">
          <summary><span class="ar">{roman}</span><span class="an">{e(name)}</span>
            <span class="ticks" aria-hidden="true">{ticks}</span><span class="rg">{a}&thinsp;&ndash;&thinsp;{z}</span></summary>
          <ol class="books">{''.join(books)}</ol>
        </details>"""


def qr_svg(url):
    qr = segno.make(url, error="m")
    size = qr.symbol_size(border=0)[0]
    d = []
    for y, row in enumerate(qr.matrix):
        x = 0
        while x < len(row):
            if row[x]:
                s0 = x
                while x < len(row) and row[x]:
                    x += 1
                d.append(f"M{s0} {y}h{x - s0}v1h-{x - s0}z")
            else:
                x += 1
    return (f'<svg viewBox="0 0 {size} {size}" role="img" aria-label="QR code for this page" '
            f'shape-rendering="crispEdges"><path fill="currentColor" d="{"".join(d)}"/></svg>')


FACES = """
@font-face{font-family:Newsreader;font-style:normal;font-weight:200 800;font-display:swap;src:url(fonts/newsreader.woff2) format("woff2");
  unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2122,U+2212}
@font-face{font-family:Newsreader;font-style:normal;font-weight:200 800;font-display:swap;src:url(fonts/newsreader-ext.woff2) format("woff2");
  unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20CF,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:Newsreader;font-style:italic;font-weight:200 800;font-display:swap;src:url(fonts/newsreader-italic.woff2) format("woff2");
  unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2122,U+2212}
@font-face{font-family:Geist;font-style:normal;font-weight:100 900;font-display:swap;src:url(fonts/geist.woff2) format("woff2")}
"""

CSS = """
/* Layout: the syllabus page, carried onto the screen. A narrow label gutter on the left,
   one reading measure beside it, hairlines between sections, and the cover art as the
   only colour on the page. */
:root{
  --paper:#FFFFFF;
  --wash:#F6F6F4;
  --ink:#121212;
  --text:#2A2A2A;
  --muted:#6E6E69;
  --faint:#C9C9C5;
  --rule:#E4E4E1;
  --signal:#D9531E;               /* the cover banner; used only for the "latest" dot */
  --serif:Newsreader,"Iowan Old Style",Georgia,serif;
  --sans:Geist,ui-sans-serif,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --gutter:120px;
  --measure:600px;
  color-scheme:light;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--text);font:400 16px/1.55 var(--sans);
  -webkit-font-smoothing:antialiased;font-kerning:normal;text-rendering:optimizeLegibility}
a{color:inherit}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px;border-radius:2px}
.page{max-width:1080px;margin:0 auto;padding-inline:max(24px,env(safe-area-inset-left));
  padding-block:max(32px,env(safe-area-inset-top)) max(48px,env(safe-area-inset-bottom))}
.label{margin:0;font:400 11px/1.3 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.dot::before{content:"";display:inline-block;width:3px;height:3px;border-radius:50%;background:currentColor;
  opacity:.55;vertical-align:middle;margin:0 .7em .15em}

/* Hero */
.hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,400px);gap:24px 72px;align-items:stretch;padding-top:24px}
.hero-text{display:flex;flex-direction:column;justify-content:space-between;gap:48px}
.hero h1{margin:0;font:330 clamp(2.6rem,1.6rem + 4vw,4.6rem)/1 var(--serif);letter-spacing:-.024em;color:var(--ink);text-wrap:balance}
.hero .sub{margin:22px 0 0;font:400 italic 20px/1.45 var(--serif);color:var(--muted);max-width:28em}
.cover{margin:0}
.cover img{display:block;width:100%;height:auto;aspect-ratio:1;border-radius:4px;
  box-shadow:0 1px 1px rgba(0,0,0,.04),0 24px 48px -24px rgba(0,0,0,.35)}
.hero-foot{grid-column:1 / -1;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
  margin-top:40px;padding-top:12px;border-top:1px solid var(--rule);font:400 13px/1.4 var(--sans);color:var(--muted)}
.hero-foot a{color:var(--ink);text-decoration:none}
.hero-foot a:hover{text-decoration:underline;text-underline-offset:3px}
.hero-foot .n{font-variant-numeric:tabular-nums}

/* Sections */
.sec{margin-top:104px}
.sec-head{display:grid;grid-template-columns:var(--gutter) minmax(0,1fr) auto;align-items:baseline;
  padding-bottom:10px;border-bottom:1px solid var(--rule);margin-bottom:36px}
.sec-head > :last-child{text-align:right;font-variant-numeric:tabular-nums;letter-spacing:.06em}
.sec-head h2{margin:0;font:400 11px/1.3 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--ink)}
.row{display:grid;grid-template-columns:var(--gutter) minmax(0,var(--measure)) minmax(0,1fr);align-items:start}
.gut{font:400 12px/1 var(--sans);color:var(--muted);font-variant-numeric:tabular-nums;letter-spacing:.04em}
.body{min-width:0}

/* Follow */
.follow .body{display:grid;gap:16px;justify-items:start}
.pill{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 20px;border-radius:999px;
  border:1px solid #D6D6D2;font:500 14.5px/1 var(--sans);color:var(--ink);text-decoration:none;white-space:nowrap;
  transition:background-color .15s ease,border-color .15s ease}
.pill:hover{background:var(--wash);border-color:#BDBDB8}
.pill-ink{min-height:52px;padding:0 30px;font-size:16px;background:var(--ink);border-color:var(--ink);color:#fff}
.pill-ink:hover{background:#000;border-color:#000}
.apps{display:flex;flex-wrap:wrap;gap:8px}
.apps:empty{display:none}
.fine{margin:0;font:400 14px/1.55 var(--sans);color:var(--muted);max-width:34em}
.feed{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:14px;width:100%;
  padding:6px 6px 6px 16px;background:var(--wash);border-radius:12px}
.feed code{font:400 13px/1.3 var(--sans);font-variant-numeric:tabular-nums;color:var(--text);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;-webkit-user-select:all;user-select:all}
.copy{min-height:36px;padding:0 14px;border-radius:999px;background:var(--paper);font:500 13px/1 var(--sans);color:var(--ink);
  box-shadow:0 0 0 1px var(--rule)}
.copy:hover{box-shadow:0 0 0 1px #BDBDB8}
.hint{margin:0;font-size:14px;color:var(--ink)}
.textlink{font:400 15px/1.4 var(--sans);color:var(--ink);text-decoration:underline;text-decoration-color:var(--faint);
  text-underline-offset:4px}
.textlink:hover{text-decoration-color:var(--ink)}
.handoff{grid-column:3;justify-self:end;display:none;width:150px}
.handoff svg{display:block;width:112px;height:112px;color:var(--ink)}
.handoff p{margin:12px 0 0;font:400 12.5px/1.45 var(--sans);color:var(--muted)}
html[data-os=mac] .handoff,html[data-os=desktop] .handoff{display:block}

details summary{list-style:none;cursor:pointer}
details summary::-webkit-details-marker{display:none}
.help{width:100%;border-top:1px solid var(--rule)}
.help summary,.fold summary{display:flex;justify-content:space-between;align-items:center;padding:14px 0;
  font:400 11px/1.3 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--ink)}
.help summary::after,.fold summary::after{content:"+";font:300 18px/1 var(--sans);letter-spacing:0;color:var(--muted)}
.help[open] summary::after,.fold[open] summary::after{content:"\\2212"}
.steps{margin:0 0 14px;padding:0;list-style:none;display:grid;gap:10px;font:400 14.5px/1.55 var(--sans);color:var(--muted)}
.steps b{font-weight:500;color:var(--ink)}

/* Episodes */
.ep + .ep{margin-top:56px;padding-top:56px;border-top:1px solid var(--rule)}
.num{font:300 40px/.9 var(--serif);color:var(--ink);letter-spacing:-.02em;font-variant-numeric:lining-nums}
.kicker{margin:0 0 10px;display:flex;gap:14px;font:400 11px/1.3 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.latest{display:none;color:var(--ink)}
.latest::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--signal);margin-right:8px;vertical-align:1px}
.is-latest .latest{display:inline}
.ep h3{margin:0;font:400 34px/1.1 var(--serif);letter-spacing:-.014em;color:var(--ink);text-wrap:balance}
.meta{margin:10px 0 0;font:400 13.5px/1.4 var(--sans);color:var(--muted)}
.summary{margin:22px 0 0;font:400 19px/1.6 var(--serif);color:var(--text);text-wrap:pretty}
.dl{margin:18px 0 0;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px}
.dl a{font:500 14.5px/1.4 var(--sans);color:var(--ink);text-decoration:underline;text-decoration-color:var(--faint);text-underline-offset:4px}
.dl a::after{content:" \\2193"}
.dl a:hover{text-decoration-color:var(--ink)}
.size{font:400 13px/1.4 var(--sans);color:var(--muted)}
.folds{margin-top:26px;border-bottom:1px solid var(--rule)}
.fold{border-top:1px solid var(--rule)}
.chapters{list-style:none;margin:0 0 16px;padding:0}
.chapters a{display:grid;grid-template-columns:64px minmax(0,1fr);gap:12px;padding:8px 0;text-decoration:none}
.ct,.ts{font:400 13px/1.7 var(--sans);font-variant-numeric:tabular-nums;color:var(--muted);text-decoration:none}
.cn{font:400 17px/1.45 var(--serif);color:var(--ink)}
.chapters a:hover .cn{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--faint)}
.transcript{max-height:62vh;overflow:auto;padding:4px 8px 18px 0;font:400 17px/1.7 var(--serif);color:var(--text)}
.transcript p{margin:0 0 16px}
.transcript .ts{margin-right:12px}
.sources{margin:0 0 18px;padding-left:1.1em;display:grid;gap:8px;font:400 14px/1.5 var(--sans);color:var(--muted)}
.sources a{color:var(--ink);text-underline-offset:3px;text-decoration-color:var(--faint)}

/* Player */
.player{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:18px;margin-top:24px;
  padding:14px 18px 14px 14px;background:var(--wash);border-radius:16px}
.player audio{display:none}
.play{width:48px;height:48px;border-radius:50%;background:var(--ink);color:#fff;display:grid;place-items:center;
  transition:transform .12s ease}
.play:active{transform:scale(.96)}
.play svg{width:22px;height:22px}
.play .i-pause,.player.playing .i-play{display:none}
.player.playing .i-pause{display:block}
.track{display:grid;gap:6px;min-width:0}
.times{display:flex;justify-content:space-between;font:400 12px/1 var(--sans);font-variant-numeric:tabular-nums;color:var(--muted)}
.seek{-webkit-appearance:none;appearance:none;width:100%;height:18px;margin:0;background:transparent;cursor:pointer}
.seek::-webkit-slider-runnable-track{height:3px;border-radius:2px;background:linear-gradient(to right,var(--ink) var(--p,0%),#DADAD6 var(--p,0%))}
.seek::-moz-range-track{height:3px;border-radius:2px;background:#DADAD6}
.seek::-moz-range-progress{height:3px;border-radius:2px;background:var(--ink)}
.seek::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:13px;height:13px;margin-top:-5px;border-radius:50%;background:var(--ink);border:0}
.seek::-moz-range-thumb{width:13px;height:13px;border-radius:50%;background:var(--ink);border:0}
.tools{display:flex;gap:2px}
.tool{min-width:38px;height:32px;border-radius:8px;font:500 12.5px/1 var(--sans);font-variant-numeric:tabular-nums;color:var(--muted)}
.tool:hover{color:var(--ink);background:rgba(0,0,0,.04)}

/* Note */
.note p{margin:0;font:400 20px/1.6 var(--serif);color:var(--text);text-wrap:pretty}
.note p + p{margin-top:14px}
.note .textlink{display:inline-block;margin-top:22px}

/* Acts */
.acts{grid-column:2 / 4;max-width:760px}
.act{border-bottom:1px solid var(--rule)}
.act:first-child{border-top:1px solid var(--rule)}
.act summary{display:grid;grid-template-columns:44px minmax(0,1fr) auto 64px;align-items:center;gap:16px;padding:15px 0}
.ar,.rg{font:400 12px/1 var(--sans);letter-spacing:.04em;color:var(--muted);font-variant-numeric:tabular-nums}
.rg{text-align:right}
.an{font:400 18px/1.35 var(--serif);color:var(--ink);text-wrap:balance}
.act summary:hover .an{text-decoration:underline;text-underline-offset:4px;text-decoration-color:var(--faint)}
.ticks{display:flex;gap:3px}
.ticks i{width:7px;height:7px;border-radius:1px;box-shadow:inset 0 0 0 1px var(--faint)}
.ticks i.on{background:var(--ink);box-shadow:none}
.act[open] .ar{color:var(--ink)}
.books{list-style:none;margin:0;padding:2px 0 22px 60px;display:grid;gap:12px}
.books li{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:12px;align-items:baseline}
.bn{font:400 12px/1 var(--sans);color:var(--muted);font-variant-numeric:tabular-nums}
.bt{display:grid;gap:3px;font:400 16.5px/1.35 var(--serif);color:var(--ink)}
.ba{font:400 13px/1.4 var(--sans);color:var(--muted)}
.listen{font:500 12px/1 var(--sans);letter-spacing:.06em;color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--faint)}
.listen::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--signal);margin-right:7px;vertical-align:1px}

footer{margin-top:120px;padding-top:14px;border-top:1px solid var(--rule);display:flex;justify-content:space-between;
  flex-wrap:wrap;gap:8px 24px;font:400 12.5px/1.4 var(--sans);color:var(--muted)}
footer nav{display:flex;gap:22px}
footer a{text-decoration:none}
footer a:hover{color:var(--ink)}

.num-inline{display:none;color:var(--ink)}

/* Phone */
@media (max-width:820px){
  :root{--gutter:0px}
  .page{padding-inline:max(20px,env(safe-area-inset-left))}
  .hero{grid-template-columns:minmax(0,1fr);gap:0;padding-top:4px}
  .hero-text{gap:0;display:block}
  .hero .label{margin-top:24px}
  .cover{order:-1;max-width:184px}
  .hero h1{margin-top:14px;font-size:clamp(2.3rem,1.4rem + 4.2vw,3rem)}
  .hero .sub{margin-top:12px;font-size:18px}
  .hero-foot{margin-top:24px}
  .sec{margin-top:64px}
  .follow{margin-top:28px}
  .follow .sec-head{display:none}
  .sec-head{margin-bottom:24px;grid-template-columns:minmax(0,1fr) auto}
  .sec-head > :nth-child(2):empty{display:none}
  .sec-head > :nth-child(2){grid-row:2;grid-column:1 / -1;margin-top:10px}
  .row{grid-template-columns:minmax(0,1fr)}
  .gut{display:none}
  .follow .body{justify-items:stretch}
  .follow .textlink{justify-self:start}
  .pill-ink{width:100%}
  .apps{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr)}
  .apps .pill{padding:0 8px;font-size:14px}
  .handoff{display:none!important}
  .num-inline{display:inline}
  .ep h3{font-size:29px}
  .summary{font-size:18px}
  .note p{font-size:18.5px}
  .acts{grid-column:1}
  .act summary{grid-template-columns:34px minmax(0,1fr) auto;grid-template-areas:"r n g" "r t t";gap:8px 12px}
  .ar{grid-area:r;align-self:start;padding-top:4px}.an{grid-area:n}.rg{grid-area:g}.ticks{grid-area:t;flex-wrap:wrap}
  .books{padding-left:0}
  .player{grid-template-columns:auto minmax(0,1fr);gap:10px 14px;padding:12px 14px}
  .tools{grid-column:1 / -1;justify-content:space-between;border-top:1px solid var(--rule);padding-top:8px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}html{scroll-behavior:auto}}
"""

JS = r"""
(function(){
  var root=document.documentElement;

  /* Lead with the right app for this device */
  var ua=navigator.userAgent||"";
  var ios=/iPhone|iPad|iPod/.test(ua)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
  var android=/Android/i.test(ua),mac=!ios&&/Macintosh/.test(ua);
  var os=ios?"ios":android?"android":mac?"mac":"desktop";
  root.setAttribute("data-os",os);
  var order={ios:["apple","overcast","pocketcasts","castro"],android:["pocketcasts","antennapod"],
             mac:["apple","pocketcasts"],desktop:["pocketcasts","apple"]}[os];
  var all={};document.querySelectorAll("[data-app]").forEach(function(a){all[a.getAttribute("data-app")]=a;});
  var slot=document.getElementById("primary"),row=document.getElementById("apps");
  slot.innerHTML="";row.innerHTML="";
  order.forEach(function(k,i){var a=all[k];if(!a)return;
    if(i===0){a.className="pill pill-ink";a.textContent="Follow in "+a.getAttribute("data-name");slot.appendChild(a);}
    else{a.className="pill";a.textContent=a.getAttribute("data-name");row.appendChild(a);}});

  /* If an app link does nothing, the page stays in front: offer the manual route */
  var hint=document.getElementById("hint"),timer=null;
  function cancel(){if(timer){clearTimeout(timer);timer=null;}}
  window.addEventListener("blur",cancel);
  document.addEventListener("visibilitychange",function(){if(document.hidden)cancel();});
  document.querySelectorAll("[data-app]").forEach(function(a){
    if(/^https?:/.test(a.getAttribute("href")))return;
    a.addEventListener("click",function(){cancel();
      timer=setTimeout(function(){if(!document.hidden&&document.hasFocus())hint.hidden=false;},2200);});});

  /* Copy the feed */
  var copy=document.getElementById("copy"),code=document.getElementById("feed-url");
  copy.addEventListener("click",function(){
    function done(){copy.textContent="Copied";setTimeout(function(){copy.textContent="Copy";},1800);}
    function fallback(){var r=document.createRange();r.selectNodeContents(code);var s=getSelection();
      s.removeAllRanges();s.addRange(r);try{document.execCommand("copy");done();}catch(e){}}
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(code.textContent).then(done,fallback);
    else fallback();});

  /* Players */
  function fmt(s){s=Math.max(0,Math.floor(s||0));var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
    return (h?h+":"+(m<10?"0":"")+m:m)+":"+(x<10?"0":"")+x;}
  var current=null;
  function setup(card){
    var p=card.querySelector(".player");if(!p||p.getAttribute("data-ready"))return;p.setAttribute("data-ready","1");
    var a=p.querySelector("audio"),play=p.querySelector(".play"),seek=p.querySelector(".seek"),
        cur=p.querySelector(".cur"),rem=p.querySelector(".rem"),rate=p.querySelector(".rate");
    var dur=+p.getAttribute("data-dur")||0,pending=null,loaded=false;
    function load(){if(!loaded){a.src=p.getAttribute("data-src");loaded=true;}}
    function D(){return a.duration&&isFinite(a.duration)?a.duration:dur;}
    function paint(){var d=D(),t=pending!=null?pending:(a.currentTime||0);seek.max=Math.max(1,Math.round(d));seek.value=t;
      cur.textContent=fmt(t);rem.textContent="−"+fmt(d-t);seek.style.setProperty("--p",(d?t/d*100:0)+"%");}
    function seekTo(t){t=Math.max(0,Math.min(t,D()||t));if(a.readyState<1){pending=t;a.preload="metadata";load();}else a.currentTime=t;paint();}
    function toggle(){if(a.paused){if(current&&current!==a)current.pause();current=a;load();a.play();}else a.pause();}
    a.addEventListener("loadedmetadata",function(){if(pending!=null){a.currentTime=pending;pending=null;}paint();});
    a.addEventListener("timeupdate",paint);
    a.addEventListener("play",function(){p.classList.add("playing");play.setAttribute("aria-label","Pause");session(card,a);});
    a.addEventListener("pause",function(){p.classList.remove("playing");play.setAttribute("aria-label","Play");});
    play.addEventListener("click",toggle);
    seek.addEventListener("input",function(){seekTo(+seek.value);});
    p.querySelector(".back").addEventListener("click",function(){seekTo((pending!=null?pending:a.currentTime||0)-15);});
    p.querySelector(".fwd").addEventListener("click",function(){seekTo((pending!=null?pending:a.currentTime||0)+30);});
    var rates=[1,1.25,1.5,2,0.8];
    rate.addEventListener("click",function(){var i=(rates.indexOf(a.playbackRate)+1)%rates.length;
      a.playbackRate=rates[i];rate.textContent=rates[i]+"×";});
    card.querySelectorAll("[data-t]").forEach(function(c){c.addEventListener("click",function(ev){
      ev.preventDefault();seekTo(+c.getAttribute("data-t"));if(a.paused)toggle();});});
    card._toggle=toggle;paint();
  }
  function session(card,a){
    if(!("mediaSession" in navigator))return;
    try{navigator.mediaSession.metadata=new MediaMetadata({title:card.getAttribute("data-title"),
      artist:"A Genealogy of Technological Optimism",album:"Episode "+card.getAttribute("data-n"),
      artwork:[{src:new URL("cover.jpg",location.href).href,sizes:"1000x1000",type:"image/jpeg"}]});
      navigator.mediaSession.setActionHandler("seekbackward",function(){a.currentTime=Math.max(0,a.currentTime-15);});
      navigator.mediaSession.setActionHandler("seekforward",function(){a.currentTime=a.currentTime+30;});}catch(e){}
  }
  document.querySelectorAll(".ep").forEach(setup);

  var listen=document.getElementById("listen-here");
  function syncListen(){var p=document.querySelector("#episode-list .player");
    if(!p){listen.hidden=true;return;}var c=p.closest(".ep");listen.hidden=false;listen.href="#"+c.id;
    listen.textContent="Or listen to episode "+c.getAttribute("data-n")+" here";}
  syncListen();
  listen.addEventListener("click",function(ev){var p=document.querySelector("#episode-list .player");if(!p)return;
    var c=p.closest(".ep");ev.preventDefault();c.scrollIntoView({behavior:"smooth",block:"start"});if(c._toggle)c._toggle();});

  /* Read the live feed when the browser allows it, so new episodes appear without a rebuild */
  var BOOKS=JSON.parse(document.getElementById("books").textContent);
  var list=document.getElementById("episode-list"),tpl=document.getElementById("ep-tpl");
  function tag(el,n){var x=el.getElementsByTagName(n)[0];return x?x.textContent:"";}
  function secs(v){if(!v)return 0;if(/^\d+$/.test(v))return +v;return v.split(":").reduce(function(t,x){return t*60+(+x||0);},0);}
  function strip(h){var d=new DOMParser().parseFromString("<div>"+h+"</div>","text/html");return (d.body.textContent||"").trim();}
  function mark(n){document.querySelectorAll('[data-n="'+n+'"]').forEach(function(el){
    if(el.tagName==="I")el.className="on";
    if(el.tagName==="LI"&&!el.classList.contains("out")){el.classList.add("out");
      var b=document.createElement("a");b.className="listen";b.href="#ep-"+n;b.textContent="Listen";el.appendChild(b);}});}
  function attach(card,url,dur){
    if(card.querySelector(".player"))return;
    var p=tpl.content.querySelector(".player").cloneNode(true);
    p.setAttribute("data-src",url);p.setAttribute("data-dur",dur||0);
    p.querySelector(".rem").textContent="−"+fmt(dur||0);
    card.querySelector(".meta").after(p);
    if(!card.querySelector(".dl")){var d=tpl.content.querySelector(".dl").cloneNode(true);
      d.querySelector("a").href=url;card.querySelector(".summary").after(d);}
    setup(card);
  }
  function make(n,desc,dur){
    var b=BOOKS[n];if(!b)return null;var c=tpl.content.querySelector(".ep").cloneNode(true);
    c.id="ep-"+n;c.setAttribute("data-n",n);c.setAttribute("data-act",b[3]);c.setAttribute("data-title",b[0]);
    c.querySelector(".num").textContent=n;c.querySelector(".num-inline").textContent=n;
    c.querySelector(".kact").textContent="Act "+b[3];c.querySelector("h3").textContent=b[0];
    var meta=c.querySelector(".meta");meta.textContent=b[1];
    [String(b[2])].concat(dur?[Math.floor(dur/60)+" min"+(dur%60?" "+dur%60+" sec":"")]:[]).forEach(function(t){
      var s=document.createElement("span");s.className="dot";s.textContent=t;meta.appendChild(s);});
    c.querySelector(".summary").textContent=desc||b[4];
    c.querySelector(".player").remove();c.querySelector(".dl").remove();
    return c;
  }
  if(window.fetch&&window.DOMParser){
    fetch(root.getAttribute("data-feed"),{mode:"cors"}).then(function(r){if(!r.ok)throw 0;return r.text();}).then(function(txt){
      var x=new DOMParser().parseFromString(txt,"application/xml");
      if(x.getElementsByTagName("parsererror").length)return;
      var items=x.getElementsByTagName("item"),seen={};
      for(var i=0;i<items.length;i++){
        var it=items[i],title=tag(it,"title"),n=parseInt(tag(it,"itunes:episode"),10);
        if(!n){var m=title.match(/^\s*(?:Episode\s*)?(\d{1,3})\b/i);n=m?+m[1]:0;}
        if(!n||!BOOKS[n]||seen[n])continue;seen[n]=1;
        var enc=it.getElementsByTagName("enclosure")[0],url=enc?enc.getAttribute("url"):"";
        if(url)url=url.replace(/^http:\/\//,"https://");
        var dur=secs(tag(it,"itunes:duration")),desc=strip(tag(it,"itunes:summary")||tag(it,"description"));
        var card=document.getElementById("ep-"+n);
        if(!card){card=make(n,desc,dur);if(!card)continue;list.appendChild(card);}
        if(url)attach(card,url,dur);
        mark(n);
      }
      var cards=[].slice.call(list.querySelectorAll(".ep")).sort(function(a,b){return b.getAttribute("data-n")-a.getAttribute("data-n");});
      cards.forEach(function(c,i){list.appendChild(c);c.classList.toggle("is-latest",i===0);});
      var count=document.querySelectorAll(".ticks i.on").length;
      document.querySelectorAll("[data-released]").forEach(function(el){el.textContent=count;});
      syncListen();
    }).catch(function(){});
  }
})();
"""


def build_html(zip_info):
    eps = "".join(episode_html(ep, i == 0) for i, ep in enumerate(EPISODES))
    acts = "".join(act_html(r, n, items) for r, n, _d, items in ACTS)
    books_json = json.dumps({b["n"]: [b["title"], b["author"], b["year"], b["roman"], b["note"]] for b in BOOKS.values()},
                            ensure_ascii=False, separators=(",", ":"))
    released = len(RELEASED)
    first = EPISODES[0]["num"]
    others = "".join(app_link(k) for k in ["overcast", "pocketcasts", "castro", "antennapod"])
    dl_all = (f'<a class="textlink" href="audio/{e(zip_info[0])}" download>Download all episodes</a>'
              if zip_info else "")
    og = f"{SITE_URL}/og.jpg"
    tpl = f"""
        <article class="ep row"><div class="gut num"></div><div class="body">
          <p class="kicker"><span class="num-inline"></span><span class="latest">Latest</span><span class="kact"></span></p><h3></h3><p class="meta"></p>
          {player_html("", 0)}<p class="summary"></p>
          <p class="dl"><a href="#" download>Download episode</a><span class="size">On iPhone, touch and hold, then tap Download Linked File.</span></p>
        </div></article>"""
    return f"""<!doctype html>
<html lang="en" data-feed="{e(FEED_FETCH)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(TITLE)}</title>
<meta name="description" content="{e(DESCRIPTION)}">
<link rel="canonical" href="{e(SITE_URL)}/">
<link rel="alternate" type="application/rss+xml" title="{e(TITLE)}" href="{e(FEED_URL)}">
<meta name="theme-color" content="#FFFFFF">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(TITLE)}">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESCRIPTION)}">
<meta property="og:url" content="{e(SITE_URL)}/">
<meta property="og:image" content="{e(og)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(TITLE)}">
<meta name="twitter:description" content="{e(DESCRIPTION)}">
<meta name="twitter:image" content="{e(og)}">
<link rel="icon" type="image/png" sizes="64x64" href="favicon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preload" href="fonts/newsreader.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/geist.woff2" as="font" type="font/woff2" crossorigin>
<style>{FACES}{CSS}</style>
</head>
<body>
<div class="page">

  <header class="hero">
    <div class="hero-text">
      <p class="label">A podcast in one hundred episodes</p>
      <div>
        <h1>A Genealogy of Technological Optimism</h1>
        <p class="sub">One hundred books in ten acts, ten minutes each.</p>
      </div>
    </div>
    <figure class="cover"><img src="cover.jpg" width="1000" height="1000" alt="Cover art: a lone figure on a ridge faces a radiant sun above power lines, a cooling tower and a city."></figure>
    <div class="hero-foot">
      <span>Created and hosted by <a href="{e(HOST_URL)}" target="_blank" rel="noopener">{e(HOST)}</a></span>
      <span class="n"><span data-released>{released}</span> of 100 released</span>
    </div>
  </header>

  <section class="sec follow" id="follow" aria-labelledby="follow-h">
    <div class="sec-head"><h2 id="follow-h">Follow</h2><span></span><span class="label">Free, in any podcast app</span></div>
    <div class="row">
      <div class="gut"></div>
      <div class="body">
        <div id="primary">{app_link("apple", True)}</div>
        <div class="apps" id="apps">{others}</div>
        <p class="fine">The show isn&rsquo;t listed in podcast directories, so search won&rsquo;t find it. These buttons add its feed straight to your app, and new episodes arrive on their own.</p>
        <div class="feed"><span class="label">RSS</span><code id="feed-url">{e(FEED_URL)}</code><button class="copy" id="copy" type="button">Copy</button></div>
        <p class="hint" id="hint" hidden>Nothing opened? Copy the feed and add it by URL in your app.</p>
        <a class="textlink" id="listen-here" href="#ep-{first}">Or listen to episode {first} here</a>
        <details class="help">
          <summary>Add it by hand, or use another app</summary>
          <ul class="steps">
            <li><b>Apple Podcasts.</b> Library, then the &hellip; menu, then Follow a Show by URL. Paste the feed.</li>
            <li><b>Overcast.</b> Tap +, then Add URL. Paste the feed.</li>
            <li><b>Pocket Casts.</b> Discover, paste the feed into search, then Subscribe.</li>
            <li><b>YouTube Music.</b> Library, Podcasts, Add podcast, then Add a podcast by RSS feed.</li>
            <li><b>Podcast Addict.</b> Tap +, then Add RSS feed. Paste the feed and tap Add.</li>
            <li><b>Spotify</b> can&rsquo;t add shows by feed URL. Any app above works.</li>
          </ul>
        </details>
      </div>
      <div class="handoff">{qr_svg(SITE_URL + "/")}<p>On your phone? Scan to open this page there.</p></div>
    </div>
  </section>

  <section class="sec episodes" aria-labelledby="eps-h">
    <div class="sec-head"><h2 id="eps-h">Episodes</h2><span>{dl_all}</span><span class="label"><span data-released>{released}</span> of 100</span></div>
    <div id="episode-list">{eps}</div>
  </section>

  <section class="sec note" aria-labelledby="note-h">
    <div class="sec-head"><h2 id="note-h">Note</h2><span></span><span></span></div>
    <div class="row"><div class="gut"></div><div class="body">
      {''.join(f'<p>{e(p)}</p>' for p in NOTE)}
      <a class="textlink" href="syllabus.pdf" target="_blank" rel="noopener">Read the syllabus, 22 pages (PDF)</a>
    </div></div>
  </section>

  <section class="sec" aria-labelledby="acts-h">
    <div class="sec-head"><h2 id="acts-h">Acts</h2><span></span><span class="label">1&thinsp;&ndash;&thinsp;100</span></div>
    <div class="row"><div class="gut"></div><div class="acts">{acts}</div></div>
  </section>

  <footer>
    <span>{e(TITLE)} &middot; {MONTH}</span>
    <nav><a href="syllabus.pdf" target="_blank" rel="noopener">Syllabus</a><a href="{e(FEED_URL)}">RSS</a><a href="{e(HOST_URL)}" target="_blank" rel="noopener">{e(HOST)}</a></nav>
  </footer>
</div>
<template id="ep-tpl">{tpl}</template>
<script type="application/json" id="books">{books_json}</script>
<script>{JS}</script>
</body>
</html>
"""


def build_assets():
    fonts = OUT / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for f in (ASSETS / "fonts").glob("*.woff2"):
        shutil.copy(f, fonts / f.name)

    cover = Image.open(COVER_SRC).convert("RGB")
    cover.resize((1000, 1000), Image.LANCZOS).save(OUT / "cover.jpg", quality=86, optimize=True, progressive=True)
    w = cover.size[0]
    sun = cover.crop((int(w * .26), int(w * .16), int(w * .74), int(w * .64)))
    sun.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png", optimize=True)
    sun.resize((64, 64), Image.LANCZOS).save(OUT / "favicon.png", optimize=True)
    if PDF_SRC.exists():
        shutil.copy(PDF_SRC, OUT / "syllabus.pdf")
    (OUT / ".nojekyll").write_text("")


def build_zip():
    local = sorted((OUT / "audio").glob("ep*.mp3")) if (OUT / "audio").exists() else []
    if len(local) < 2:
        return None
    nums = [int(p.stem[2:]) for p in local]
    name = f"Genealogy-of-Technological-Optimism-episodes-{min(nums)}-{max(nums)}.zip"
    with zipfile.ZipFile(OUT / "audio" / name, "w", zipfile.ZIP_STORED) as z:
        for p, n in zip(local, nums):
            z.write(p, f"{n:02d} {BOOKS[n]['title']}.mp3")
    return name, (OUT / "audio" / name).stat().st_size / 1e6


def build_og():
    from playwright.sync_api import sync_playwright
    tmp = OUT / "_og.html"
    tmp.write_text(f"""<!doctype html><meta charset="utf-8"><style>{FACES}
html,body{{margin:0;width:1200px;height:630px;background:#fff;color:#121212}}
.wrap{{display:grid;grid-template-columns:1fr 470px;gap:64px;padding:0 72px;align-items:center;height:630px}}
img{{width:470px;height:470px;display:block;border-radius:4px;box-shadow:0 30px 60px -30px rgba(0,0,0,.4)}}
.t{{display:flex;flex-direction:column;justify-content:space-between;height:470px}}
.e{{font:400 15px/1 Geist;letter-spacing:.16em;text-transform:uppercase;color:#6E6E69}}
h1{{font:330 64px/1 Newsreader;letter-spacing:-.024em;margin:0}}
.s{{margin:18px 0 0;font:400 italic 26px/1.4 Newsreader;color:#6E6E69}}
.f{{border-top:1px solid #E4E4E1;padding-top:14px;font:400 17px/1 Geist;color:#6E6E69}}
</style><div class="wrap"><div class="t"><div class="e">A podcast</div>
<div><h1>A Genealogy of Technological Optimism</h1><p class="s">One hundred books in ten acts.</p></div>
<div class="f">Created and hosted by Jon Slotkin</div></div><img src="cover.jpg"></div>""")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        pg.goto(tmp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT / "og.png"))
        b.close()
    Image.open(OUT / "og.png").convert("RGB").save(OUT / "og.jpg", quality=90, optimize=True)
    (OUT / "og.png").unlink()
    tmp.unlink()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for item in OUT.iterdir():          # keep published audio; rebuild everything else
        if item.name == "audio":
            for z in item.glob("*.zip"):
                z.unlink()
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    build_assets()
    doc = build_html(None)
    zi = build_zip()
    if zi:
        doc = build_html(zi)
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    build_og()
    print("built", OUT, "| site:", SITE_URL, "| episodes:", sorted(RELEASED))
