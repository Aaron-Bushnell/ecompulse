#!/usr/bin/env python3
"""
PyInstaller build script for 实习岗位采集器.

Usage:
    pip install pyinstaller
    pip install -r requirements.txt
    python build_exe.py

Output: dist/实习岗位采集器/实习岗位采集器.exe (self-contained directory)
"""

import os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "竞品监控"


def find_playwright_browsers():
    """Locate ms-playwright directory for bundling."""
    candidates = [
        Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")),
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "AppData" / "Local" / "ms-playwright",
    ]
    for c in candidates:
        if c and c.exists() and list(c.iterdir()):
            return c
    return None


def build():
    print("[build] Installing Playwright Chromium (if needed)...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       check=True, capture_output=True)
    except Exception:
        print("[build] WARNING: Chromium install failed — browser crawlers won't work in EXE")

    # Clean
    for d in [ROOT / "dist", ROOT / "build"]:
        if d.exists():
            shutil.rmtree(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--noconfirm",
        "--clean",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build'}",
        "--add-data", f"internship_tracker{os.pathsep}internship_tracker",
        "--collect-all", "openpyxl",
        "--collect-all", "playwright",
    ]

    pw_path = find_playwright_browsers()
    if pw_path:
        cmd.extend(["--add-binary", f"{pw_path}{os.pathsep}ms-playwright"])
        print(f"[build] Bundling Playwright browsers: {pw_path}")

    cmd.append(str(ROOT / "main.py"))

    print(f"[build] Running PyInstaller...")
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    out = ROOT / "dist" / APP_NAME / (APP_NAME + ".exe")
    print(f"\n[build] Done: {out}")
    print(f"[build] Distribute the entire '{ROOT / 'dist' / APP_NAME}' folder.")


if __name__ == "__main__":
    build()
