#!/usr/bin/env python3
"""Download the word list to words.txt.  Run explicitly; never run by the game."""

import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = ("https://raw.githubusercontent.com/first20hours/google-10000-english/"
       "master/google-10000-english-no-swears.txt")
DESTINATION = Path(__file__).resolve().parent / "words.txt"


def main() -> int:
    """Fetch the list as text and save it (the content is never executed)."""
    try:
        with urllib.request.urlopen(URL, timeout=15) as response:
            data = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    if not data.strip():
        print("Download returned an empty file; nothing saved.", file=sys.stderr)
        return 1
    try:
        DESTINATION.write_text(data, encoding="utf-8")
    except OSError as exc:
        print(f"Could not write {DESTINATION}: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {len(data.splitlines())} lines to {DESTINATION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
