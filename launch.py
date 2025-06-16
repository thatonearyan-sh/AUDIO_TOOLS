#!/usr/bin/env python3
"""
audio — Aryan Audio Toolkit launcher
Choose between Terminal CLI or Web Browser UI.
"""
import sys
import os
import subprocess
import time
from pathlib import Path

TOOLKIT_DIR = Path(__file__).parent
CLI_SCRIPT  = TOOLKIT_DIR / "audio_toolkit.py"
WEB_SCRIPT  = TOOLKIT_DIR / "web" / "server.py"
PORT        = 7171

# ── ANSI colours ──────────────────────────────────────────────────────────────
C  = "\033[96m"   # cyan
M  = "\033[95m"   # magenta
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
W  = "\033[97m"   # white
D  = "\033[2m"    # dim
R  = "\033[0m"    # reset
B  = "\033[1m"    # bold

def banner():
    print(f"""
{C}{B}  ╔══════════════════════════════════════════╗
  ║      🎵  Aryan Audio Toolkit  🎵         ║
  ║  Crop · Merge · Mix · Convert · Fade     ║
  ╚══════════════════════════════════════════╝{R}
""")

def menu():
    banner()
    print(f"  {W}{B}How do you want to use the toolkit?{R}\n")
    print(f"  {C}{B}[1]{R}  {W}🖥️  Terminal CLI{R}   {D}— arrow-key menus, drag & drop path{R}")
    print(f"  {M}{B}[2]{R}  {W}🌐  Web Browser{R}    {D}— beautiful UI, opens at localhost:{PORT}{R}")
    print(f"  {D}[q]  Quit{R}")
    print()

    while True:
        try:
            choice = input(f"  {Y}Choose [1/2/q]:{R} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {D}Bye!{R}\n")
            sys.exit(0)

        if choice in ('1', 'cli', 'c', 'terminal', 't'):
            launch_cli()
            break
        elif choice in ('2', 'web', 'w', 'browser', 'b'):
            launch_web()
            break
        elif choice in ('q', 'quit', 'exit', ''):
            print(f"\n  {D}Bye!{R}\n")
            sys.exit(0)
        else:
            print(f"  {Y}⚠  Type 1, 2, or q{R}")


def launch_cli():
    print(f"\n  {C}→ Launching Terminal CLI...{R}\n")
    os.execv(sys.executable, [sys.executable, str(CLI_SCRIPT)])


def launch_web():
    print(f"\n  {M}→ Starting web server on http://localhost:{PORT}{R}")
    print(f"  {D}  Press Ctrl+C to stop the server{R}\n")

    # Open browser after a short delay
    try:
        import threading, webbrowser, time
        def _open():
            time.sleep(1.4)
            webbrowser.open(f"http://localhost:{PORT}")
        threading.Thread(target=_open, daemon=True).start()
    except Exception:
        pass

    # Run the Flask server
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    try:
        subprocess.run([sys.executable, str(WEB_SCRIPT)], env=env)
    except KeyboardInterrupt:
        print(f"\n\n  {D}Web server stopped.{R}\n")

def cleanup_7days():
    """Delete files older than 7 days from uploads and outputs."""
    cutoff = time.time() - (7 * 24 * 3600)  # 7 days ago
    for folder in [".web_uploads", "WebOutputs"]:
        d = TOOLKIT_DIR / folder
        if not d.exists(): continue
        for f in d.iterdir():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    cleanup_7days()
    
    # Direct flags: audio --web  or  audio --cli
    args = sys.argv[1:]
    if args and args[0] in ('--web', '-w', 'web'):
        banner()
        launch_web()
    elif args and args[0] in ('--cli', '-c', 'cli'):
        launch_cli()
    else:
        menu()
