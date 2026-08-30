#!/usr/bin/env python3
"""Record a captioned walkthrough of the public Streamlit demo.

Uses the live Cloud URL (same paper keys). Does not place orders. Does not
fake a fill. HOLD is an allowed tape.

  .venv/bin/pip install playwright
  .venv/bin/playwright install chromium
  .venv/bin/python scripts/record_demo_video.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_URL = (
    "https://bszv8nabdvvipmbetdvtgv.streamlit.app/"
    "?embed=true&embed_options=dark_theme"
)
SHORT_URL = "bszv8nabdvvipmbetdvtgv.streamlit.app"
FONT = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
W, H, FPS = 1280, 720, 30

POINTER_JS = """
() => {
  let d = document.getElementById("veto-pointer");
  if (!d) {
    d = document.createElement("div");
    d.id = "veto-pointer";
    d.style.cssText = [
      "position:fixed", "z-index:2147483647", "width:22px", "height:22px",
      "margin-left:-3px", "margin-top:-3px", "border-radius:50%",
      "border:2px solid #e11d2e", "background:rgba(225,29,46,0.35)",
      "box-shadow:0 0 0 4px rgba(225,29,46,0.12)", "pointer-events:none",
      "left:40px", "top:40px",
    ].join(";");
    document.documentElement.appendChild(d);
    window.addEventListener("mousemove", (e) => {
      d.style.left = e.clientX + "px";
      d.style.top = e.clientY + "px";
    }, true);
  }
}
"""


class Narration:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.events: list[tuple[float, str]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def say(self, text: str) -> None:
        self.events.append((self.now(), text))
        print(f"[{self.now():6.1f}s] {text}", flush=True)


def wrap_ass(text: str, width: int = 64) -> str:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if len(trial) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return r"\N".join(lines)


def ass_time(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def write_ass(path: Path, events: list[tuple[float, str]], duration: float) -> None:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Noto Sans,28,&H00FFFFFF,&H000000FF,&H66000000,&HAA000000,"
        "0,0,0,0,100,100,0,0,3,0,0,2,48,48,36,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for i, (start, text) in enumerate(events):
        if i + 1 < len(events):
            end = events[i + 1][0] - 0.12
        else:
            end = duration - 0.15
        end = max(start + 3.4, min(end, start + 9.5))
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,"
            f"{wrap_ass(text)}"
        )
    path.write_text("\n".join(lines) + "\n")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def loc(page, selector: str | None = None, **kwargs):
    frame = page.frame_locator("iframe[src*='/~/+']")
    if selector:
        return frame.locator(selector)
    if "role" in kwargs:
        return frame.get_by_role(kwargs.pop("role"), **kwargs)
    if "text" in kwargs:
        return frame.get_by_text(kwargs.pop("text"), **kwargs)
    raise ValueError("need selector or role/text")


def ensure_pointer(page) -> None:
    try:
        page.frame_locator("iframe[src*='/~/+']").locator("body").evaluate(POINTER_JS)
    except Exception:
        pass


def human_click(page, target, pause_ms: int = 320) -> None:
    ensure_pointer(page)
    target.scroll_into_view_if_needed()
    page.wait_for_timeout(pause_ms)
    target.hover()
    page.wait_for_timeout(220)
    target.click(delay=110)
    page.wait_for_timeout(400)
    ensure_pointer(page)


def record_walkthrough(url: str, raw_webm: Path, narration: Narration) -> None:
    from playwright.sync_api import sync_playwright

    raw_webm.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(raw_webm.parent / "takes"),
            record_video_size={"width": W, "height": H},
            color_scheme="dark",
        )
        page = context.new_page()
        page.set_default_timeout(120_000)
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        loc(page, text="The model may research").first.wait_for(timeout=120_000)
        loc(page, text="Equity").first.wait_for()
        ensure_pointer(page)
        page.wait_for_timeout(800)
        narration.t0 = time.monotonic()

        narration.say(
            "This is the public Streamlit demo — same Alpaca paper account as the laptop loop. Fake money. One hundred thousand dollars."
        )
        page.wait_for_timeout(5200)

        narration.say(
            "Equity and cash are still a hundred k. Options approved, not halted. We will not fake a fill just to move these numbers."
        )
        page.wait_for_timeout(4800)

        tape = loc(page, text="Paper account tape").first
        tape.scroll_into_view_if_needed()
        ensure_pointer(page)
        tape.hover()
        narration.say(
            "The tape is live from those paper keys. Empty until a real SMA cross fills. That is honest — not a broken demo."
        )
        page.wait_for_timeout(5500)

        scan_btn = loc(page, role="button", name="Run dry scan")
        scan_btn.scroll_into_view_if_needed()
        narration.say(
            "Dry scan on closed daily bars. HOLD is allowed. Veto will not invent a buy so the table looks exciting."
        )
        page.wait_for_timeout(1800)
        human_click(page, scan_btn)
        loc(page, text="buy intent").first.wait_for(timeout=120_000)
        result = loc(page, text="0 buy intent").or_(loc(page, text="no_fresh_cross")).first
        result.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        if loc(page, text="no_fresh_cross").count() > 0:
            narration.say(
                "Every name is HOLD — no fresh cross. The reason column is the veto. Zero buy intents, and that is a valid tape."
            )
        else:
            narration.say(
                "A real fresh cross showed up. The desk still has to pass check_entry before anything is sized. Nothing in this app can place that order."
            )
        page.wait_for_timeout(5200)

        explain_btn = loc(page, role="button", name="Explain")
        explain_btn.scroll_into_view_if_needed()
        narration.say(
            "Explain reads the desk. Cloud has no laptop ledger, so you will often see no_decision. The operator loop keeps the real reasons."
        )
        page.wait_for_timeout(1400)
        human_click(page, explain_btn)
        loc(page, text="no_decision").or_(loc(page, text="halted")).first.wait_for(timeout=30_000)
        loc(page, text="no_decision").or_(loc(page, text="Explain a decision")).first.scroll_into_view_if_needed()
        page.wait_for_timeout(4500)

        collar_btn = loc(page, role="button", name="Preview collar")
        collar_btn.scroll_into_view_if_needed()
        narration.say(
            "Collar preview prices a defined-risk overlay through Alpaca. About eight percent out of the money. It prints a CLI string. It does not submit."
        )
        page.wait_for_timeout(1400)
        human_click(page, collar_btn)
        loc(page, text="Alpaca CLI string").or_(loc(page, text="no_collar_contracts")).first.wait_for(
            timeout=90_000
        )
        loc(page, text="Alpaca CLI string").or_(loc(page, text='"cli"')).first.scroll_into_view_if_needed()
        page.wait_for_timeout(5800)

        halt = loc(page, text="Halt status").first
        halt.scroll_into_view_if_needed()
        narration.say(
            "Halt is read-only. There is no buy button, no execute, and no reconcile here. The model may research. Veto decides."
        )
        page.wait_for_timeout(900)
        human_click(page, halt)
        page.wait_for_timeout(4200)

        footer = loc(page, text="This demo cannot place orders").first
        footer.scroll_into_view_if_needed()
        page.wait_for_timeout(2800)

        video = page.video
        page.close()
        if video is None:
            context.close()
            browser.close()
            raise RuntimeError("Playwright did not record a video")
        video.save_as(str(raw_webm))
        context.close()
        browser.close()


def ffmpeg_available() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("ffmpeg is required to burn captions and title cards")
    return exe


def make_still(ffmpeg: str, out: Path, lines: list[tuple[str, int, int]], seconds: float, bg: Path | None) -> None:
    """lines: (text, fontsize, y)"""
    if bg and bg.exists():
        vf = [
            f"scale={W}:{H}:force_original_aspect_ratio=increase",
            f"crop={W}:{H}",
        ]
        src = ["-loop", "1", "-i", str(bg)]
    else:
        vf = []
        src = ["-f", "lavfi", "-i", f"color=c=0x111111:s={W}x{H}:r={FPS}"]
    for i, (text, size, y) in enumerate(lines):
        textfile = out.parent / f"{out.stem}_line{i}.txt"
        textfile.write_text(text)
        font = FONT_BOLD if i == 0 else FONT
        vf.append(
            "drawtext=fontfile={font}:textfile={tf}:reload=0:"
            "x=(w-text_w)/2:y={y}:fontsize={size}:fontcolor=white:"
            "borderw=0:shadowx=0:shadowy=0".format(
                font=font, tf=textfile, y=y, size=size
            )
        )
    vf.append(f"fps={FPS},setsar=1")
    run(
        [
            ffmpeg, "-y", *src, "-t", f"{seconds:.2f}",
            "-vf", ",".join(vf),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-an", str(out),
        ]
    )


def watermark_and_subs(ffmpeg: str, src: Path, ass: Path, dst: Path) -> None:
    url_file = dst.parent / "url.txt"
    url_file.write_text(SHORT_URL)
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},setsar=1,"
        f"drawtext=fontfile={FONT}:textfile={url_file}:"
        "x=w-text_w-20:y=16:fontsize=18:fontcolor=white:"
        "box=1:boxcolor=black@0.55:boxborderw=8,"
        f"subtitles={ass}:fontsdir=/usr/share/fonts/noto"
    )
    run(
        [
            ffmpeg, "-y", "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-an", str(dst),
        ]
    )


def concat(ffmpeg: str, parts: list[Path], dst: Path) -> None:
    listing = dst.parent / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run(
        [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", "-an", str(dst),
        ]
    )


def render(out_dir: Path, raw_webm: Path, narration: Narration) -> Path:
    ffmpeg = ffmpeg_available()
    title = out_dir / "title.mp4"
    end = out_dir / "end.mp4"
    walk = out_dir / "walk.mp4"
    final = out_dir / "veto-demo-preview.mp4"
    cover = REPO / "docs" / "cover.png"

    make_still(
        ffmpeg,
        title,
        [
            ("Live paper demo", 26, H - 118),
            (SHORT_URL, 22, H - 78),
        ],
        6.0,
        cover,
    )
    make_still(
        ffmpeg,
        end,
        [
            ("The model may research. Veto decides.", 32, 280),
            ("No buy button. Paper only. HOLD is allowed.", 24, 360),
            (f"{SHORT_URL}   ·   github.com/dancaldera/veto", 20, 460),
        ],
        6.5,
        None,
    )

    ffprobe = shutil.which("ffprobe") or "ffprobe"
    probe = subprocess.check_output(
        [
            ffprobe,
            "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", str(raw_webm),
        ],
        text=True,
    ).strip()
    duration = float(probe)
    ass = out_dir / "captions.ass"
    write_ass(ass, narration.events, duration)
    watermark_and_subs(ffmpeg, raw_webm, ass, walk)
    concat(ffmpeg, [title, walk, end], final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", type=Path, default=REPO / "docs" / "video")
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "raw.webm"
    narration = Narration()
    print(f"Recording {args.url}", flush=True)
    record_walkthrough(args.url, raw, narration)
    final = render(out_dir, raw, narration)
    print(f"Wrote {final}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModuleNotFoundError as exc:
        if "playwright" in str(exc):
            sys.stderr.write("Install Playwright in the venv: .venv/bin/pip install playwright && .venv/bin/playwright install chromium\n")
        raise
