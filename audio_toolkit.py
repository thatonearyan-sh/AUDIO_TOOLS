#!/usr/bin/env python3
from __future__ import annotations
"""
╔═══════════════════════════════════════════════════════╗
║           🎵  Aryan Audio Toolkit  🎵                 ║
║   Crop · Merge · Mix · Convert · Fade · Reverse       ║
╚═══════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import curses
import json
from pathlib import Path

# ─── Dependency check ────────────────────────────────────────────────────────
def check_deps():
    missing = []
    try:
        from pydub import AudioSegment
    except ImportError:
        missing.append("pydub")
    try:
        from rich.console import Console
    except ImportError:
        missing.append("rich")
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   Run: pip3 install {' '.join(missing)}")
        sys.exit(1)

check_deps()

# ─── Imports ─────────────────────────────────────────────────────────────────
from pydub import AudioSegment
from pydub.effects import speedup
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.align import Align
import shutil

console = Console()

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp'}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

# ─── Output Location Config ───────────────────────────────────────────────────

DESKTOP_FOLDER  = Path.home() / "Desktop" / "AudioToolkitOutputs"
DOT_FOLDER_NAME = ".audio_outputs"   # created next to the input file

SAVE_OPTIONS = [
    {
        "key":   "dot",
        "icon":  "📁",
        "label": "Hidden folder next to source",
        "sub":   ".audio_outputs/  (beside your file)",
        "desc":  "Creates a hidden .audio_outputs/ folder in the same directory as the input",
    },
    {
        "key":   "desktop",
        "icon":  "🖥️ ",
        "label": "Desktop folder",
        "sub":   "~/Desktop/AudioToolkitOutputs/",
        "desc":  "Saves to a dedicated folder on your Desktop — easy to find",
    },
    {
        "key":   "both",
        "icon":  "✨",
        "label": "Both places",
        "sub":   ".audio_outputs/  +  Desktop/AudioToolkitOutputs/",
        "desc":  "Saves a copy to both locations simultaneously",
    },
]


def resolve_output_paths(input_path: str, filename: str, choice: str) -> list[str]:
    """Return 1 or 2 full output paths given the save choice key."""
    p = Path(input_path)
    paths = []
    if choice in ("dot", "both"):
        d = p.parent / DOT_FOLDER_NAME
        d.mkdir(parents=True, exist_ok=True)
        paths.append(str(d / filename))
    if choice in ("desktop", "both"):
        DESKTOP_FOLDER.mkdir(parents=True, exist_ok=True)
        paths.append(str(DESKTOP_FOLDER / filename))
    return paths


# ═════════════════════════════════════════════════════════════════════════════
#  PER-OPERATION SAVE LOCATION PICKER  (curses, 3 options)
# ═════════════════════════════════════════════════════════════════════════════

def pick_save_location(input_path: str, suffix: str, ext: str = None) -> list[str]:
    """
    Show an arrow-key curses screen with 3 save-location choices.
    Returns a list of full output file paths (1 or 2 items).
    Returns [] if cancelled.
    """
    p = Path(input_path)
    out_ext  = ext if ext else p.suffix
    filename = f"{p.stem}_{suffix}{out_ext}"

    result = {"choice": None}

    def _picker(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,    -1)   # normal option
        curses.init_pair(2, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # selected
        curses.init_pair(3, curses.COLOR_YELLOW,  -1)   # heading
        curses.init_pair(4, curses.COLOR_GREEN,   -1)   # desc / sub
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)   # footer / divider

        idx = 0

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # ── Header ──
            title = f"  💾  Where to save:  {filename}  "
            try:
                stdscr.addstr(1, max(0, (w - len(title)) // 2), title,
                              curses.color_pair(3) | curses.A_BOLD)
                stdscr.addstr(2, 0, "─" * w, curses.color_pair(5))
            except curses.error:
                pass

            # ── Options ──
            row = 4
            for i, opt in enumerate(SAVE_OPTIONS):
                is_sel = i == idx
                col    = curses.color_pair(2) | curses.A_BOLD if is_sel else curses.color_pair(1)
                prefix = "  ▶ " if is_sel else "    "

                main_line = f"{prefix}{opt['icon']}  {opt['label']}"
                sub_line  = f"       {opt['sub']}"

                try:
                    stdscr.addstr(row,     2, main_line[:w - 4], col)
                    stdscr.addstr(row + 1, 2, sub_line[:w - 4],
                                  curses.color_pair(4) if is_sel else curses.color_pair(5))
                    if is_sel:
                        stdscr.addstr(row + 2, 7, f"↳ {opt['desc']}"[:w - 9],
                                      curses.color_pair(4))
                except curses.error:
                    pass

                row += 4

            # ── Footer ──
            footer = " ↑↓ Navigate   Enter: Confirm   Q: Cancel "
            try:
                stdscr.addstr(h - 2, max(0, (w - len(footer)) // 2), footer,
                              curses.color_pair(5) | curses.A_BOLD)
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_UP, ord('k')):
                idx = (idx - 1) % len(SAVE_OPTIONS)
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = (idx + 1) % len(SAVE_OPTIONS)
            elif key in (curses.KEY_ENTER, 10, 13):
                result["choice"] = SAVE_OPTIONS[idx]["key"]
                return
            elif key in (ord('q'), ord('Q'), 27):
                return

    curses.wrapper(_picker)

    if result["choice"] is None:
        return []

    return resolve_output_paths(input_path, filename, result["choice"])


def do_save(audio: AudioSegment, out_paths: list[str], label: str = "Saved"):
    """Save audio to all chosen paths and print success for each."""
    if not out_paths:
        console.print("\n[yellow]⚠  Save cancelled.[/yellow]")
        return
    for out in out_paths:
        save_audio(audio, out)
        success(f"{label} → {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  CURSES FILE BROWSER
# ═════════════════════════════════════════════════════════════════════════════

def file_browser(start_dir: str = None, audio_only: bool = True) -> str | None:
    """Interactive arrow-key file browser. Returns selected file path or None."""
    start_dir = Path(start_dir or Path.home()).expanduser().resolve()

    result = {"path": None}

    def _browser(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,    -1)   # directory
        curses.init_pair(2, curses.COLOR_GREEN,   -1)   # audio file
        curses.init_pair(3, curses.COLOR_WHITE,   -1)   # other file
        curses.init_pair(4, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # selected
        curses.init_pair(5, curses.COLOR_YELLOW,  -1)   # header
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)   # footer

        current_dir = start_dir
        selected_idx = 0
        scroll_offset = 0

        def get_entries(directory):
            entries = []
            try:
                if directory != directory.parent:
                    entries.append((".. (Go Back)", directory.parent, "parent"))
                items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                for item in items:
                    if item.name.startswith('.'):
                        continue
                    if item.is_dir():
                        entries.append((f"📁 {item.name}/", item, "dir"))
                    elif item.suffix.lower() in AUDIO_EXTENSIONS:
                        entries.append((f"🎵 {item.name}", item, "audio"))
                    elif not audio_only:
                        entries.append((f"   {item.name}", item, "file"))
            except PermissionError:
                pass
            return entries

        entries = get_entries(current_dir)

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            header_txt = f" 🎵 Aryan Audio Toolkit — File Browser "
            stdscr.addstr(0, 0, header_txt.center(w), curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(1, 0, f" 📂 {current_dir} ".ljust(w), curses.color_pair(1))
            stdscr.addstr(2, 0, "─" * w, curses.color_pair(6))

            list_start_row = 3
            list_height = h - 7
            visible_entries = entries[scroll_offset: scroll_offset + list_height]

            for i, (label, path, kind) in enumerate(visible_entries):
                actual_idx = scroll_offset + i
                is_selected = actual_idx == selected_idx

                if kind in ("dir", "parent"):
                    color = curses.color_pair(1) | curses.A_BOLD
                elif kind == "audio":
                    color = curses.color_pair(2)
                else:
                    color = curses.color_pair(3)

                if is_selected:
                    color = curses.color_pair(4) | curses.A_BOLD

                display = f"  {label:<{w-4}}"
                try:
                    stdscr.addstr(list_start_row + i, 0, display[:w], color)
                except curses.error:
                    pass

            footer_row = h - 3
            stdscr.addstr(footer_row, 0, "─" * w, curses.color_pair(6))
            footer = " ↑↓ Navigate   Enter: Select/Open   P: Paste Path   Q: Cancel "
            stdscr.addstr(footer_row + 1, 0, footer.center(w), curses.color_pair(6) | curses.A_BOLD)

            if len(entries) > list_height:
                pct = int((scroll_offset / max(1, len(entries) - list_height)) * 100)
                stdscr.addstr(footer_row + 2, 0,
                              f" {scroll_offset+1}-{min(scroll_offset+list_height, len(entries))}/{len(entries)}  [{pct}%] ",
                              curses.color_pair(5))

            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_UP, ord('k')):
                if selected_idx > 0:
                    selected_idx -= 1
                    if selected_idx < scroll_offset:
                        scroll_offset = selected_idx

            elif key in (curses.KEY_DOWN, ord('j')):
                if selected_idx < len(entries) - 1:
                    selected_idx += 1
                    if selected_idx >= scroll_offset + list_height:
                        scroll_offset += 1

            elif key in (curses.KEY_ENTER, 10, 13):
                if not entries:
                    continue
                label, path, kind = entries[selected_idx]
                if kind in ("dir", "parent"):
                    current_dir = path
                    entries = get_entries(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                elif kind == "audio":
                    result["path"] = str(path)
                    return

            elif key in (ord('p'), ord('P')):
                curses.echo()
                curses.curs_set(1)
                prompt_row = max(0, h - 3)          # avoid writing on last line
                prompt_str = (" Enter path: " + " " * w)[:w - 1]  # clamp to terminal width
                try:
                    stdscr.addstr(prompt_row, 0, prompt_str)
                    stdscr.move(prompt_row, 13)
                except curses.error:
                    pass
                raw = stdscr.getstr(prompt_row, 13, w - 14).decode("utf-8", errors="ignore").strip()
                curses.noecho()
                curses.curs_set(0)
                # Handle macOS drag-drop escaping (e.g. "/path/my\ file.mp3")
                raw = raw.strip("'\"" ).replace("\\ ", " ")
                if raw and Path(raw).is_dir():
                    current_dir = Path(raw).resolve()
                    entries = get_entries(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                elif raw and Path(raw).is_file():
                    result["path"] = str(Path(raw).resolve())
                    return

            elif key in (ord('q'), ord('Q'), 27):
                return

            elif key == curses.KEY_BACKSPACE:
                if current_dir != current_dir.parent:
                    current_dir = current_dir.parent
                    entries = get_entries(current_dir)
                    selected_idx = 0
                    scroll_offset = 0

    curses.wrapper(_browser)
    return result["path"]


# ═════════════════════════════════════════════════════════════════════════════
#  ARROW-KEY MAIN MENU
# ═════════════════════════════════════════════════════════════════════════════

MENU_ITEMS = [
    ("✂️  Crop / Trim Audio",        "crop",    "Cut audio between two timestamps"),
    ("🔗  Merge / Concatenate",      "merge",   "Join 2+ audio files end-to-end"),
    ("🔀  Overlay / Mix",            "overlay", "Play 2 audios at the same time"),
    ("🔊  Volume Control",           "volume",  "Increase or decrease volume (dB)"),
    ("🔄  Convert Format",           "convert", "Convert between MP3, WAV, OGG, FLAC..."),
    ("⏩  Change Speed",             "speed",   "Speed up or slow down audio"),
    ("🌅  Fade In / Fade Out",       "fade",    "Add smooth fade effects"),
    ("📊  Audio Info",               "info",    "Show duration, sample rate, channels"),
    ("🔁  Reverse Audio",            "reverse", "Reverse the playback of audio"),
    ("✂️✂️ Extract Multiple Segments", "multi",  "Cut multiple clips from one file"),
    ("🔇  Silence Remover",          "silence", "Remove silent parts from audio"),
    ("🔉  Normalize Volume",         "normalize","Auto-balance volume to a target level"),
    ("🎬  Extract Audio from Video", "video",   "Rip audio track from MP4, MKV, AVI..."),
    ("📝  Transcribe (Speech-to-Text)", "transcribe", "Extract text from audio/video"),
    ("❌  Exit",                      "exit",    ""),
]


def arrow_menu() -> str:
    """Full-screen arrow-key menu. Returns action key."""
    result = {"action": "exit"}

    def _menu(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,    -1)
        curses.init_pair(2, curses.COLOR_BLACK,   curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_YELLOW,  -1)
        curses.init_pair(4, curses.COLOR_GREEN,   -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)

        idx = 0

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # ── Banner ──
            banner_lines = [
                "  ╔══════════════════════════════════════╗  ",
                "  ║      🎵  Aryan Audio Toolkit  🎵     ║  ",
                "  ║  Crop·Merge·Mix·Convert·Fade·More    ║  ",
                "  ╚══════════════════════════════════════╝  ",
            ]
            row = 1
            for line in banner_lines:
                x = max(0, (w - len(line)) // 2)
                try:
                    stdscr.addstr(row, x, line, curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass
                row += 1

            # ── Save-location reminder ──
            hint = "  💾 You'll choose where to save after each operation  "
            try:
                stdscr.addstr(row, max(0, (w - len(hint)) // 2), hint, curses.color_pair(4))
            except curses.error:
                pass
            row += 2

            title = "  Select an operation:  "
            try:
                stdscr.addstr(row, max(0, (w - len(title)) // 2), title,
                              curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass
            row += 1

            for i, (label, action, desc) in enumerate(MENU_ITEMS):
                is_sel = i == idx
                col = curses.color_pair(2) | curses.A_BOLD if is_sel else curses.color_pair(1)

                prefix = "  ▶ " if is_sel else "    "
                line = f"{prefix}{label:<38}"
                x = max(0, (w - 50) // 2)
                try:
                    stdscr.addstr(row + i, x, line[:w - x], col)
                    if is_sel and desc:
                        hint_txt = f"  ↳ {desc}"
                        stdscr.addstr(row + i, x + len(line) + 2,
                                      hint_txt[:max(0, w - x - len(line) - 3)],
                                      curses.color_pair(4))
                except curses.error:
                    pass

            footer = " ↑↓ Navigate   Enter: Choose   Q: Quit "
            try:
                stdscr.addstr(h - 2, max(0, (w - len(footer)) // 2), footer,
                              curses.color_pair(5) | curses.A_BOLD)
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                idx = (idx - 1) % len(MENU_ITEMS)
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = (idx + 1) % len(MENU_ITEMS)
            elif key in (curses.KEY_ENTER, 10, 13):
                result["action"] = MENU_ITEMS[idx][1]
                return
            elif key in (ord('q'), ord('Q'), 27):
                result["action"] = "exit"
                return

    curses.wrapper(_menu)
    return result["action"]


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def header(title: str, subtitle: str = ""):
    console.print()
    content = Text(title, style="bold cyan")
    if subtitle:
        content.append(f"\n{subtitle}", style="dim white")
    console.print(Panel(Align.center(content), border_style="cyan", padding=(1, 4)))
    console.print()


def success(msg: str):
    console.print(f"\n✅ [bold green]{msg}[/bold green]")


def err(msg: str):
    console.print(f"\n❌ [bold red]{msg}[/bold red]")


def info(msg: str):
    console.print(f"   [dim white]{msg}[/dim white]")


def pick_file(prompt_text: str = "Select audio file", start_dir: str = None) -> str | None:
    """
    Ask for a file path. Supports:
      - Drag & drop  (macOS pastes escaped path automatically)
      - Typing / pasting a path
      - Type 'b' to open the arrow-key file browser
    """
    console.print(f"\n[bold cyan]📂 {prompt_text}[/bold cyan]")
    console.print("[dim]  Drag & drop a file here  •  or type / paste path  •  or type [bold]b[/bold] to browse[/dim]\n")

    while True:
        raw = Prompt.ask("   [yellow]→[/yellow]", default="").strip()

        if not raw:
            return None

        # 'b' opens the curses browser
        if raw.lower() == 'b':
            console.print("[dim]  Opening file browser...[/dim]")
            time.sleep(0.3)
            path = file_browser(start_dir=start_dir)
            if path:
                console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        # Clean up macOS drag-drop formatting:
        #   /path/to/my\ file.mp3  →  /path/to/my file.mp3
        #   '/path/to/file.mp3'   →  /path/to/file.mp3
        path = raw.strip("'\"" ).replace("\\ ", " ")

        if not Path(path).exists():
            err(f"Not found: {path}")
            console.print("   [dim]Try again, drop a different file, or type 'b' to browse[/dim]\n")
            continue

        if Path(path).is_file():
            if Path(path).suffix.lower() not in AUDIO_EXTENSIONS:
                err(f"Not a supported audio file: {Path(path).name}")
                console.print(f"   [dim]Supported: {', '.join(sorted(AUDIO_EXTENSIONS))}[/dim]\n")
                continue
            console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        err("Path is a directory, not a file.")
        console.print("   [dim]Drop a file, not a folder.[/dim]\n")


def pick_video_file(prompt_text: str = "Select video file", start_dir: str = None) -> str | None:
    """Ask for a video file path. Supports drag & drop, typing, or 'b' browser."""
    console.print(f"\n[bold cyan]🎬 {prompt_text}[/bold cyan]")
    console.print("[dim]  Drag & drop a video here  •  or type / paste path  •  or type [bold]b[/bold] to browse[/dim]\n")

    while True:
        raw = Prompt.ask("   [yellow]→[/yellow]", default="").strip()

        if not raw:
            return None

        if raw.lower() == 'b':
            console.print("[dim]  Opening file browser...[/dim]")
            time.sleep(0.3)
            path = file_browser(start_dir=start_dir, audio_only=False)
            if path:
                console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        path = raw.strip("'\"" ).replace("\\ ", " ")

        if not Path(path).exists():
            err(f"Not found: {path}")
            console.print("   [dim]Try again, or type 'b' to browse[/dim]\n")
            continue

        if Path(path).is_file():
            if Path(path).suffix.lower() not in VIDEO_EXTENSIONS:
                err(f"Not a supported video file: {Path(path).name}")
                console.print(f"   [dim]Supported: {', '.join(sorted(VIDEO_EXTENSIONS))}[/dim]\n")
                continue
            console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        err("Path is a directory, not a file.")
        console.print("   [dim]Drop a file, not a folder.[/dim]\n")


def pick_media_file(prompt_text: str = "Select media file", start_dir: str = None) -> str | None:
    """Ask for an audio or video file path."""
    console.print(f"\n[bold cyan]📂 {prompt_text}[/bold cyan]")
    console.print("[dim]  Drag & drop a file here  •  or type / paste path  •  or type [bold]b[/bold] to browse[/dim]\n")

    while True:
        raw = Prompt.ask("   [yellow]→[/yellow]", default="").strip()

        if not raw:
            return None

        if raw.lower() == 'b':
            console.print("[dim]  Opening file browser...[/dim]")
            time.sleep(0.3)
            path = file_browser(start_dir=start_dir, audio_only=False)
            if path:
                console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        path = raw.strip("'\"" ).replace("\\ ", " ")

        if not Path(path).exists():
            err(f"Not found: {path}")
            console.print("   [dim]Try again, or type 'b' to browse[/dim]\n")
            continue

        if Path(path).is_file():
            if Path(path).suffix.lower() not in MEDIA_EXTENSIONS:
                err(f"Not a supported audio/video file: {Path(path).name}")
                console.print(f"   [dim]Supported: {', '.join(sorted(MEDIA_EXTENSIONS))}[/dim]\n")
                continue
            console.print(f"   [green]✓ Selected:[/green] [bold]{Path(path).name}[/bold]")
            return path

        err("Path is a directory, not a file.")
        console.print("   [dim]Drop a file, not a folder.[/dim]\n")

def parse_time(t: str) -> int:
    """Parse '1:23.5' or '83.5' or '83' into milliseconds."""
    t = t.strip()
    try:
        if ':' in t:
            parts = t.split(':')
            minutes = int(parts[0])
            seconds = float(parts[1])
            return int((minutes * 60 + seconds) * 1000)
        else:
            return int(float(t) * 1000)
    except (ValueError, IndexError):
        raise ValueError(f"Invalid time format: '{t}'. Use MM:SS or seconds (e.g. 1:30 or 90)")


def ms_to_str(ms: int) -> str:
    total_sec = ms / 1000
    minutes = int(total_sec // 60)
    seconds = total_sec % 60
    return f"{minutes}:{seconds:05.2f}"


def load_audio(path: str) -> AudioSegment:
    ext = Path(path).suffix.lower().lstrip('.')
    ext = ext if ext else 'mp3'
    with Progress(SpinnerColumn(), TextColumn("[cyan]Loading audio..."), transient=True) as p:
        p.add_task("", total=None)
        audio = AudioSegment.from_file(path, format=ext)
    return audio


def save_audio(audio: AudioSegment, output_path: str):
    ext = Path(output_path).suffix.lower().lstrip('.')
    ext = ext if ext else 'mp3'
    with Progress(SpinnerColumn(), TextColumn("[cyan]Saving..."), BarColumn(), transient=True) as p:
        p.add_task("", total=None)
        audio.export(output_path, format=ext)


def make_suffix(s: str) -> str:
    """Sanitise a string for use in a filename."""
    return s.replace(':', 'm').replace('/', '-').replace(' ', '_')


def show_audio_info_table(path: str, audio: AudioSegment):
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column("Key",   style="bold cyan",  no_wrap=True)
    table.add_column("Value", style="bold white")

    duration_ms = len(audio)
    table.add_row("📄 File",         Path(path).name)
    table.add_row("⏱️  Duration",     ms_to_str(duration_ms))
    table.add_row("🎚️  Channels",     str(audio.channels))
    table.add_row("📻 Sample Rate",  f"{audio.frame_rate} Hz")
    table.add_row("🔢 Sample Width", f"{audio.sample_width * 8} bit")
    table.add_row("📦 Frame Count",  f"{audio.frame_count():,.0f}")
    table.add_row("💾 File Size",    f"{Path(path).stat().st_size / 1024:.1f} KB")

    console.print(table)


# ═════════════════════════════════════════════════════════════════════════════
#  OPERATIONS
# ═════════════════════════════════════════════════════════════════════════════

def op_crop():
    header("✂️  Crop / Trim Audio", "Cut audio between two timestamps")

    path = pick_file("Select audio to crop")
    if not path: return

    audio = load_audio(path)
    dur = len(audio)
    console.print(f"\n   [cyan]Duration:[/cyan] [bold]{ms_to_str(dur)}[/bold]  ({dur/1000:.1f}s total)")
    console.print("   [dim]Time format: MM:SS (e.g. 1:30) or seconds (e.g. 90)[/dim]\n")

    start_str = Prompt.ask("   [yellow]Start time[/yellow]", default="0")
    end_str   = Prompt.ask("   [yellow]End time  [/yellow]", default=ms_to_str(dur))

    try:
        start_ms = parse_time(start_str)
        end_ms   = parse_time(end_str)
    except ValueError as e:
        err(str(e)); return

    if start_ms >= end_ms:
        err("Start time must be before end time."); return
    if end_ms > dur:
        end_ms = dur
        console.print("   [yellow]⚠  End time clamped to audio duration.[/yellow]")

    cropped = audio[start_ms:end_ms]
    suffix  = f"crop_{make_suffix(ms_to_str(start_ms))}-{make_suffix(ms_to_str(end_ms))}"

    out_paths = pick_save_location(path, suffix)
    do_save(cropped, out_paths, "Cropped audio saved")
    if out_paths:
        info(f"Duration: {ms_to_str(len(cropped))}")


def op_merge():
    header("🔗 Merge / Concatenate Audio", "Join multiple audio files end-to-end")

    files = []
    console.print("   [dim]Add files one by one. Leave blank when done.[/dim]\n")

    while True:
        label = f"Select audio #{len(files)+1}" + (" (or skip to finish)" if files else "")
        path = pick_file(label)
        if not path:
            if len(files) < 2:
                err("Need at least 2 files to merge.")
                continue
            break
        files.append(path)
        console.print(f"   [green]✓ Added:[/green] {Path(path).name}")
        if len(files) >= 2:
            again = Confirm.ask("   Add another file?", default=False)
            if not again: break

    if len(files) < 2:
        err("Not enough files."); return

    console.print(f"\n   [cyan]Merging {len(files)} files...[/cyan]")
    with Progress(SpinnerColumn(), TextColumn("[cyan]Loading and joining..."), transient=True) as p:
        p.add_task("", total=None)
        combined = AudioSegment.empty()
        for f in files:
            combined += load_audio(f)

    out_paths = pick_save_location(files[0], "merged", ext=Path(files[0]).suffix)
    do_save(combined, out_paths, "Merged audio saved")
    if out_paths:
        info(f"Total duration: {ms_to_str(len(combined))}")


def op_overlay():
    header("🔀 Overlay / Mix Audio", "Play two audios simultaneously (e.g. voice + music)")

    console.print("   [dim]Select the base audio (e.g. your voice recording)[/dim]")
    path1 = pick_file("Select BASE audio")
    if not path1: return

    console.print("\n   [dim]Select the overlay audio (e.g. background music)[/dim]")
    path2 = pick_file("Select OVERLAY audio")
    if not path2: return

    audio1 = load_audio(path1)
    audio2 = load_audio(path2)

    console.print(f"\n   [cyan]Base    duration:[/cyan] {ms_to_str(len(audio1))}")
    console.print(f"   [cyan]Overlay duration:[/cyan] {ms_to_str(len(audio2))}")

    overlay_vol = Prompt.ask("\n   [yellow]Overlay volume adjustment dB (e.g. -10 to quieten)[/yellow]", default="-6")
    try:
        overlay_db = float(overlay_vol)
    except ValueError:
        overlay_db = -6.0

    audio2_adj = audio2 + overlay_db
    if len(audio2_adj) < len(audio1):
        loops = (len(audio1) // len(audio2_adj)) + 1
        audio2_adj = audio2_adj * loops

    mixed = audio1.overlay(audio2_adj)

    out_paths = pick_save_location(path1, "mixed")
    do_save(mixed, out_paths, "Mixed audio saved")


def op_volume():
    header("🔊 Volume Control", "Increase or decrease volume in dB")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    console.print(f"\n   [dim]Positive dB = louder, negative dB = quieter[/dim]")
    console.print(f"   [dim]Examples: +6 (2x louder), -6 (half volume), +10, -20[/dim]\n")

    db_str = Prompt.ask("   [yellow]Volume change (dB)[/yellow]", default="+3")
    try:
        db = float(db_str.replace('+', ''))
    except ValueError:
        err("Invalid dB value."); return

    adjusted = audio + db

    sign   = '+' if db >= 0 else ''
    suffix = f"vol{sign}{int(db)}dB"
    out_paths = pick_save_location(path, suffix)
    do_save(adjusted, out_paths, f"Volume adjusted {db:+.1f} dB")


def op_convert():
    header("🔄 Convert Format", "Convert audio between different formats")

    formats = ["mp3", "wav", "ogg", "flac", "aac", "opus"]
    console.print("   [dim]Supported formats: " + ", ".join(formats) + "[/dim]\n")

    path = pick_file("Select audio to convert")
    if not path: return

    fmt = Prompt.ask("   [yellow]Output format[/yellow]", choices=formats, default="mp3")
    audio = load_audio(path)

    out_paths = pick_save_location(path, "converted", ext=f".{fmt}")
    do_save(audio, out_paths, f"Converted to {fmt.upper()}")


def op_speed():
    header("⏩ Change Speed", "Speed up or slow down audio")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    console.print(f"\n   [dim]1.0 = normal, 2.0 = 2x speed, 0.5 = half speed[/dim]")
    console.print(f"   [dim]Recommended range: 0.5 – 3.0[/dim]\n")

    speed_str = Prompt.ask("   [yellow]Speed factor[/yellow]", default="1.5")
    try:
        speed = float(speed_str)
        if speed <= 0:
            raise ValueError()
    except ValueError:
        err("Invalid speed value."); return

    with Progress(SpinnerColumn(), TextColumn("[cyan]Changing speed..."), transient=True) as p:
        p.add_task("", total=None)
        if speed > 1.0:
            result_audio = speedup(audio, playback_speed=speed)
        else:
            slowed = audio._spawn(audio.raw_data, overrides={
                "frame_rate": int(audio.frame_rate * speed)
            })
            result_audio = slowed.set_frame_rate(audio.frame_rate)

    out_paths = pick_save_location(path, f"speed{speed}x")
    do_save(result_audio, out_paths, f"Speed changed to {speed}x")
    if out_paths:
        info(f"Original: {ms_to_str(len(audio))}  →  New: {ms_to_str(len(result_audio))}")


def op_fade():
    header("🌅 Fade In / Fade Out", "Add smooth fade effects to audio")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    console.print(f"\n   [cyan]Duration:[/cyan] {ms_to_str(len(audio))}\n")

    apply_in  = Confirm.ask("   Apply [bold]Fade In[/bold]?",  default=True)
    apply_out = Confirm.ask("   Apply [bold]Fade Out[/bold]?", default=True)

    if not apply_in and not apply_out:
        err("No effect selected."); return

    fin_ms = fout_ms = 0
    if apply_in:
        fin_str = Prompt.ask("   [yellow]Fade-in duration (seconds)[/yellow]", default="3")
        try: fin_ms = int(float(fin_str) * 1000)
        except: fin_ms = 3000

    if apply_out:
        fout_str = Prompt.ask("   [yellow]Fade-out duration (seconds)[/yellow]", default="3")
        try: fout_ms = int(float(fout_str) * 1000)
        except: fout_ms = 3000

    result_audio = audio
    if apply_in:  result_audio = result_audio.fade_in(fin_ms)
    if apply_out: result_audio = result_audio.fade_out(fout_ms)

    out_paths = pick_save_location(path, "faded")
    do_save(result_audio, out_paths, "Faded audio saved")


def op_info():
    header("📊 Audio Info", "Show detailed audio file information")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    console.print()
    show_audio_info_table(path, audio)
    console.print()


def op_reverse():
    header("🔁 Reverse Audio", "Reverse the playback direction")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    with Progress(SpinnerColumn(), TextColumn("[cyan]Reversing audio..."), transient=True) as p:
        p.add_task("", total=None)
        reversed_audio = audio.reverse()

    out_paths = pick_save_location(path, "reversed")
    do_save(reversed_audio, out_paths, "Reversed audio saved")


def op_multi_segment():
    header("✂️✂️ Extract Multiple Segments", "Cut multiple clips from one audio file")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    dur = len(audio)
    console.print(f"\n   [cyan]Duration:[/cyan] {ms_to_str(dur)}")
    console.print("   [dim]Define segments as: START END  (e.g. 0:30 1:00)[/dim]")
    console.print("   [dim]Press Enter with empty input when done.[/dim]\n")

    segments = []
    seg_num = 1
    while True:
        seg_input = Prompt.ask(f"   [yellow]Segment {seg_num} (start end)[/yellow]", default="").strip()
        if not seg_input:
            if not segments:
                err("Add at least one segment.")
                continue
            break
        parts = seg_input.split()
        if len(parts) != 2:
            err("Format: START END  (e.g. 0:30 1:00)"); continue
        try:
            s, e = parse_time(parts[0]), parse_time(parts[1])
            if s >= e: raise ValueError("Start >= End")
            segments.append((s, e))
            console.print(f"   [green]✓ Segment {seg_num}:[/green] {ms_to_str(s)} → {ms_to_str(e)}  ({(e-s)/1000:.1f}s)")
            seg_num += 1
        except ValueError as ex:
            err(str(ex))

    # Ask once where to save all segments
    console.print(f"\n   [dim]Now choose where to save all {len(segments)} segment(s)...[/dim]")
    # We use the first segment as representative for the location picker
    first_suffix = f"seg1_{make_suffix(ms_to_str(segments[0][0]))}-{make_suffix(ms_to_str(segments[0][1]))}"
    sample_paths = pick_save_location(path, first_suffix)
    if not sample_paths:
        console.print("\n[yellow]⚠  Save cancelled.[/yellow]")
        return

    # Derive chosen mode from which dirs were selected
    dirs_chosen = [str(Path(p).parent) for p in sample_paths]

    for i, (s, e) in enumerate(segments, 1):
        clip = audio[s:e]
        ext  = Path(path).suffix
        clip_name = f"{Path(path).stem}_seg{i}_{make_suffix(ms_to_str(s))}-{make_suffix(ms_to_str(e))}{ext}"
        for out_dir in dirs_chosen:
            clip_path = str(Path(out_dir) / clip_name)
            save_audio(clip, clip_path)
            console.print(f"   [green]✓ Saved segment {i}:[/green] {clip_path}")

    success(f"Extracted {len(segments)} segments to {len(dirs_chosen)} location(s)")


def op_silence_remover():
    header("🔇 Silence Remover", "Remove silent parts from audio")

    path = pick_file("Select audio file")
    if not path: return

    from pydub.silence import split_on_silence

    audio = load_audio(path)
    console.print(f"\n   [cyan]Duration:[/cyan] {ms_to_str(len(audio))}\n")

    thresh_str  = Prompt.ask("   [yellow]Silence threshold (dBFS, e.g. -40)[/yellow]", default="-40")
    min_sil_str = Prompt.ask("   [yellow]Min silence duration to remove (ms)[/yellow]",  default="500")
    padding_str = Prompt.ask("   [yellow]Keep padding around speech (ms)[/yellow]",       default="200")

    try:
        thresh  = float(thresh_str)
        min_sil = int(min_sil_str)
        padding = int(padding_str)
    except ValueError:
        err("Invalid input."); return

    with Progress(SpinnerColumn(), TextColumn("[cyan]Detecting silence..."), transient=True) as p:
        p.add_task("", total=None)
        chunks = split_on_silence(audio, min_silence_len=min_sil,
                                  silence_thresh=thresh, keep_silence=padding)

    if not chunks:
        err("No speech detected. Try adjusting the threshold."); return

    combined = AudioSegment.empty()
    for chunk in chunks:
        combined += chunk

    console.print(f"\n   [cyan]Removed:[/cyan] {ms_to_str(len(audio) - len(combined))} of silence")
    console.print(f"   [cyan]Result: [/cyan] {ms_to_str(len(combined))}")

    out_paths = pick_save_location(path, "no_silence")
    do_save(combined, out_paths, "Silence-removed audio saved")


def op_normalize():
    header("🔉 Normalize Volume", "Auto-balance volume to a target level")

    path = pick_file("Select audio file")
    if not path: return

    audio = load_audio(path)
    target_str = Prompt.ask("\n   [yellow]Target loudness (dBFS, e.g. -14 for streaming standard)[/yellow]", default="-14")
    try:
        target = float(target_str)
    except ValueError:
        err("Invalid value."); return

    current_loudness = audio.dBFS
    console.print(f"\n   [cyan]Current loudness:[/cyan] {current_loudness:.1f} dBFS")
    console.print(f"   [cyan]Target loudness :[/cyan] {target:.1f} dBFS")

    change     = target - current_loudness
    normalized = audio + change

    out_paths = pick_save_location(path, "normalized")
    do_save(normalized, out_paths, f"Normalized to {target:.1f} dBFS")
    if out_paths:
        info(f"Volume adjusted by {change:+.1f} dB")


def op_extract_video():
    header("🎬 Extract Audio from Video", "Rip the audio track from any video file")

    path = pick_video_file("Select a video file")
    if not path: return

    import subprocess

    # Get video duration via ffprobe
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30
        )
        total_sec = float(probe.stdout.strip())
        total_ms  = int(total_sec * 1000)
    except Exception:
        total_sec = 0
        total_ms  = 0

    if total_ms > 0:
        console.print(f"\n   [cyan]Video duration:[/cyan] [bold]{ms_to_str(total_ms)}[/bold]  ({total_sec:.1f}s total)")
    else:
        console.print(f"\n   [yellow]⚠  Could not detect video duration.[/yellow]")

    # Ask for output format
    fmt = Prompt.ask("   [yellow]Output audio format[/yellow]", default="mp3",
                     choices=["mp3", "wav", "flac", "aac", "ogg", "opus"])

    # Ask about trimming
    console.print("\n   [dim]Do you want the full audio or a specific segment?[/dim]")
    console.print("   [dim]Time format: MM:SS (e.g. 1:30) or seconds (e.g. 90)[/dim]\n")

    start_str = Prompt.ask("   [yellow]Start time[/yellow] (blank = beginning)", default="0")
    end_str   = Prompt.ask("   [yellow]End time  [/yellow] (blank = end)", default="")

    try:
        start_ms = parse_time(start_str)
    except ValueError:
        start_ms = 0

    end_ms = None
    if end_str:
        try:
            end_ms = parse_time(end_str)
            if end_ms <= start_ms:
                err("End time must be after start time."); return
        except ValueError as e:
            err(str(e)); return

    # Build suffix
    if start_ms == 0 and end_ms is None:
        suffix = "extracted"
    else:
        s_tag = make_suffix(ms_to_str(start_ms))
        e_tag = make_suffix(ms_to_str(end_ms)) if end_ms else "end"
        suffix = f"extract_{s_tag}-{e_tag}"

    out_paths = pick_save_location(path, suffix, ext=f".{fmt}")
    if not out_paths:
        return

    for out in out_paths:
        Path(out).parent.mkdir(parents=True, exist_ok=True)

        cmd = ["ffmpeg", "-y", "-i", path]

        if start_ms > 0:
            cmd += ["-ss", str(start_ms / 1000)]
        if end_ms is not None:
            duration_sec = (end_ms - start_ms) / 1000
            cmd += ["-t", str(duration_sec)]

        cmd += ["-vn"]   # no video

        if fmt == "mp3":
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
        elif fmt == "wav":
            cmd += ["-acodec", "pcm_s16le"]
        elif fmt == "flac":
            cmd += ["-acodec", "flac"]
        elif fmt == "aac":
            cmd += ["-acodec", "aac", "-b:a", "192k"]
        elif fmt == "ogg":
            cmd += ["-acodec", "libvorbis", "-q:a", "5"]
        elif fmt == "opus":
            cmd += ["-acodec", "libopus", "-b:a", "128k"]

        cmd.append(out)

        with Progress(SpinnerColumn(), TextColumn("[cyan]Extracting audio from video..."), transient=True) as p:
            p.add_task("", total=None)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            err(f"ffmpeg error: {result.stderr[-300:] if result.stderr else 'unknown error'}")
            return

        success(f"Audio extracted → {out}")

    if out_paths:
        extracted = AudioSegment.from_file(out_paths[0], format=fmt)
        info(f"Duration: {ms_to_str(len(extracted))}")


def op_transcribe():
    header("📝 Transcribe (Speech-to-Text)", "Extract spoken words from audio or video files")

    # Use pick_media_file since it accepts both audio and video extensions via ffmpeg
    path = pick_media_file("Select an audio or video file to transcribe")
    if not path: return

    try:
        import speech_recognition as sr
        import tempfile
        r = sr.Recognizer()
        
        audio = load_audio(path)
        chunk_ms = 60000  # 60 seconds
        full_text = []
        
        with Progress(SpinnerColumn(), TextColumn("[cyan]Transcribing..."), BarColumn(), transient=True) as p:
            task = p.add_task("", total=len(audio))
            
            for i in range(0, len(audio), chunk_ms):
                chunk = audio[i:i+chunk_ms]
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav:
                    chunk.export(temp_wav.name, format="wav")
                    with sr.AudioFile(temp_wav.name) as source:
                        audio_data = r.record(source)
                        try:
                            text = r.recognize_google(audio_data)
                            full_text.append(text)
                        except sr.UnknownValueError:
                            pass
                        except sr.RequestError as e:
                            err(f"Speech API Error: {e}")
                            return
                p.update(task, advance=len(chunk))
                        
        final_text = "\n\n".join(full_text)
        if not final_text.strip():
            final_text = "(No speech could be recognized)"
            
        console.print("\n[bold green]📝 Transcription Complete:[/bold green]")
        console.print(Panel(final_text, border_style="green", padding=(1, 2)))
        
        save_txt = Confirm.ask("\n[cyan]Save transcription to a text file?[/cyan]", default=True)
        if save_txt:
            out_paths = pick_save_location(path, "transcript", ext=".txt")
            if out_paths:
                for out in out_paths:
                    Path(out).parent.mkdir(parents=True, exist_ok=True)
                    Path(out).write_text(final_text)
                    success(f"Saved transcript → {out}")
                    
    except ImportError:
        err("SpeechRecognition library not installed.")
        console.print("   [dim]Run: pip3 install SpeechRecognition[/dim]")
    except Exception as e:
        err(f"Unexpected error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═════════════════════════════════════════════════════════════════════════════

OP_MAP = {
    "crop":      op_crop,
    "merge":     op_merge,
    "overlay":   op_overlay,
    "volume":    op_volume,
    "convert":   op_convert,
    "speed":     op_speed,
    "fade":      op_fade,
    "info":      op_info,
    "reverse":   op_reverse,
    "multi":     op_multi_segment,
    "silence":   op_silence_remover,
    "normalize": op_normalize,
    "video":     op_extract_video,
    "transcribe": op_transcribe,
}


def main():
    while True:
        action = arrow_menu()

        if action == "exit":
            console.print("\n[bold cyan]👋 Goodbye! Happy editing 🎵[/bold cyan]\n")
            sys.exit(0)

        fn = OP_MAP.get(action)
        if fn:
            try:
                fn()
            except KeyboardInterrupt:
                console.print("\n\n[yellow]⚠ Operation cancelled.[/yellow]")
            except Exception as e:
                err(f"Unexpected error: {e}")
                console.print_exception(show_locals=False)

        console.print()
        again = Confirm.ask("[cyan]Return to main menu?[/cyan]", default=True)
        if not again:
            console.print("\n[bold cyan]👋 Goodbye! Happy editing 🎵[/bold cyan]\n")
            break


if __name__ == "__main__":
    main()
