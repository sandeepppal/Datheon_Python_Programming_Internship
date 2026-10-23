#!/usr/bin/env python3
"""Console Hangman game (Datheon Python Programming Internship).

Game logic (``GameState``) is separate from input validation, word loading,
rendering and the interactive loop, so the logic can be tested without a
keyboard.  Uses the Python standard library only.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
MAX_WRONG_GUESSES = 6
DEFAULT_WORDS_FILE = Path(__file__).resolve().parent / "words.txt"

# Word-length range (inclusive) per difficulty level.
DIFFICULTIES: dict[str, tuple[int, int]] = {
    "easy": (4, 6),
    "medium": (5, 8),
    "hard": (8, 14),
}
DEFAULT_DIFFICULTY = "medium"

# Small built-in list used only when words.txt is missing or unusable.
FALLBACK_WORDS: tuple[str, ...] = (
    "python", "variable", "function", "program", "keyboard", "internet",
    "database", "compiler", "software", "network", "algorithm", "library",
    "terminal", "iteration", "boolean", "integer", "string", "module",
    "package", "debugging", "developer", "computer", "monitor", "browser",
    "gallows", "puzzle", "letter", "player", "victory",
    "defeat", "attempt", "garden", "bridge", "planet", "rocket",
    "mountain", "journey", "penguin", "diamond", "chicken", "balance",
    "context", "science", "student", "teacher", "history",
    "morning", "country", "holiday", "silver", "market", "window",
)

# Seven stages: index == number of incorrect guesses (0..6).
_GALLOWS_TEMPLATE = (
    "  +---+",
    "  |   |",
    "  {head}   |",
    " {l_arm}{body}{r_arm}  |",
    " {l_leg} {r_leg}  |",
    "      |",
    "=========",
)


def _build_stage(wrong: int) -> str:
    """Return the gallows drawing for ``wrong`` incorrect guesses."""
    parts = {
        "head": "O" if wrong >= 1 else " ",
        "body": "|" if wrong >= 2 else " ",
        "l_arm": "/" if wrong >= 3 else " ",
        "r_arm": "\\" if wrong >= 4 else " ",
        "l_leg": "/" if wrong >= 5 else " ",
        "r_leg": "\\" if wrong >= 6 else " ",
    }
    return "\n".join(line.format(**parts) for line in _GALLOWS_TEMPLATE)


GALLOWS_STAGES: tuple[str, ...] = tuple(
    _build_stage(n) for n in range(MAX_WRONG_GUESSES + 1)
)


# --------------------------------------------------------------------------
# Word list loading and validation
# --------------------------------------------------------------------------
def normalize_word(raw: str) -> Optional[str]:
    """Return a lowercase playable word, or ``None`` if unsuitable.

    A playable word is non-empty, ASCII and purely alphabetic.
    """
    word = raw.strip().lower()
    if word and word.isascii() and word.isalpha():
        return word
    return None


def clean_words(raw_words: Iterable[str]) -> list[str]:
    """Normalize, validate and de-duplicate words, keeping original order."""
    cleaned = (normalize_word(w) for w in raw_words)
    return list(dict.fromkeys(w for w in cleaned if w))


def load_words(path: Path) -> list[str]:
    """Load valid words from a UTF-8 text file (one word per line).

    Raises:
        OSError: file missing or unreadable.
        UnicodeDecodeError: file is not valid UTF-8.
        ValueError: file contains no usable words.
    """
    text = path.read_text(encoding="utf-8")
    words = clean_words(text.splitlines())
    if not words:
        raise ValueError(f"No usable words found in {path}")
    return words


def load_words_with_fallback(path: Path) -> tuple[list[str], Optional[str]]:
    """Load ``path``; on any problem return the fallback list and a message."""
    try:
        return load_words(path), None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        note = (
            f"Note: could not use word list ({exc}).\n"
            "      Using the small built-in list. See README for how to "
            "download words.txt."
        )
        return clean_words(FALLBACK_WORDS), note


def select_word(
    words: Sequence[str],
    min_len: int,
    max_len: int,
    rng: Optional[random.Random] = None,
) -> str:
    """Pick a random word whose length is within ``[min_len, max_len]``.

    Raises:
        ValueError: no word matches the length range.
    """
    candidates = [w for w in words if min_len <= len(w) <= max_len]
    if not candidates:
        raise ValueError(f"No words with length {min_len}-{max_len}")
    return (rng or random).choice(candidates)


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------
def validate_guess(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Validate raw input.  Returns ``(letter, None)`` or ``(None, error)``."""
    text = raw.strip()
    if not text:
        return None, "Please enter a letter (input was empty)."
    if len(text) > 1:
        return None, "Please enter exactly one letter at a time."
    if not (text.isascii() and text.isalpha()):
        return None, "Only letters A-Z are allowed (no digits or symbols)."
    return text.lower(), None


# --------------------------------------------------------------------------
# Game logic
# --------------------------------------------------------------------------
class GuessResult(Enum):
    """Outcome of applying one valid letter to the game."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    REPEATED = "repeated"


@dataclass
class GameState:
    """All state for one game of Hangman."""

    secret: str
    max_wrong: int = MAX_WRONG_GUESSES
    guessed: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.secret = self.secret.lower()

    @property
    def wrong_letters(self) -> list[str]:
        """Incorrect guesses, alphabetical."""
        return sorted(c for c in self.guessed if c not in self.secret)

    @property
    def wrong_count(self) -> int:
        return len(self.wrong_letters)

    @property
    def remaining(self) -> int:
        """Attempts left; never negative."""
        return max(0, self.max_wrong - self.wrong_count)

    @property
    def is_won(self) -> bool:
        return all(c in self.guessed for c in self.secret)

    @property
    def is_lost(self) -> bool:
        return self.wrong_count >= self.max_wrong and not self.is_won

    @property
    def is_over(self) -> bool:
        return self.is_won or self.is_lost

    def masked_word(self) -> str:
        """Secret with unguessed letters hidden, e.g. ``_ A _ H``."""
        return " ".join(c.upper() if c in self.guessed else "_" for c in self.secret)

    def guess(self, letter: str) -> GuessResult:
        """Apply a single validated lowercase letter.

        Raises:
            ValueError: game already over, or ``letter`` is not one a-z letter.
        """
        if self.is_over:
            raise ValueError("The game is already over.")
        if len(letter) != 1 or not letter.isalpha():
            raise ValueError("A guess must be a single letter.")
        letter = letter.lower()
        if letter in self.guessed:
            return GuessResult.REPEATED
        self.guessed.add(letter)
        return GuessResult.CORRECT if letter in self.secret else GuessResult.INCORRECT


@dataclass
class SessionStats:
    """Win/loss counts for one run of the program."""

    wins: int = 0
    losses: int = 0

    @property
    def played(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return 100.0 * self.wins / self.played if self.played else 0.0

    def record(self, state: GameState) -> None:
        """Record a finished game."""
        if state.is_won:
            self.wins += 1
        elif state.is_lost:
            self.losses += 1


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
LINE = "=" * 44


def render_board(state: GameState) -> str:
    """Return the full game screen as text."""
    guessed = " ".join(c.upper() for c in sorted(state.guessed)) or "(none)"
    wrong = " ".join(c.upper() for c in state.wrong_letters) or "(none)"
    return "\n".join([
        LINE,
        GALLOWS_STAGES[min(state.wrong_count, MAX_WRONG_GUESSES)],
        "",
        f"  Word:       {state.masked_word()}",
        f"  Attempts:   {state.remaining} of {state.max_wrong} remaining",
        f"  Guessed:    {guessed}",
        f"  Incorrect:  {wrong}",
        LINE,
    ])


def render_victory(state: GameState) -> str:
    """Victory screen."""
    return "\n".join([
        "*" * 44,
        "   YOU WIN!  The word was: " + state.secret.upper(),
        f"   Wrong guesses: {state.wrong_count}/{state.max_wrong}"
        f"   Letters tried: {len(state.guessed)}",
        "*" * 44,
    ])


def render_defeat(state: GameState) -> str:
    """Defeat screen (reveals the secret word)."""
    return "\n".join([
        "x" * 44,
        "   GAME OVER.  The word was: " + state.secret.upper(),
        f"   Wrong guesses: {state.wrong_count}/{state.max_wrong}"
        f"   Letters tried: {len(state.guessed)}",
        "x" * 44,
    ])


def render_stats(stats: SessionStats) -> str:
    """One-line session summary."""
    return (f"Session: {stats.played} played, {stats.wins} won, "
            f"{stats.losses} lost, win rate {stats.win_rate:.0f}%")


# --------------------------------------------------------------------------
# Interactive loop
# --------------------------------------------------------------------------
InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def play_game(
    state: GameState,
    input_fn: Optional[InputFn] = None,
    output_fn: Optional[OutputFn] = None,
) -> GameState:
    """Run one game until it ends.  I/O is injectable for testing."""
    input_fn = input_fn or input
    output_fn = output_fn or print
    while not state.is_over:
        output_fn(render_board(state))
        letter, error = validate_guess(input_fn("Guess a letter: "))
        if error or letter is None:
            output_fn(f"Invalid input: {error}")
            continue
        result = state.guess(letter)
        if result is GuessResult.REPEATED:
            output_fn(f"You already guessed '{letter.upper()}'. "
                      "No attempt was used.")
        elif result is GuessResult.CORRECT:
            output_fn(f"Good guess! '{letter.upper()}' is in the word.")
        else:
            output_fn(f"Sorry, '{letter.upper()}' is not in the word.")
    output_fn(render_board(state))
    output_fn(render_victory(state) if state.is_won else render_defeat(state))
    return state


def ask_replay(input_fn: Optional[InputFn] = None) -> bool:
    """Ask until the player answers yes or no."""
    input_fn = input_fn or input
    while True:
        answer = input_fn("Play again? (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Console Hangman game.")
    parser.add_argument("--words", type=Path, default=DEFAULT_WORDS_FILE,
                        help="path to a UTF-8 word list (default: words.txt "
                             "next to this script)")
    parser.add_argument("--difficulty", choices=sorted(DIFFICULTIES),
                        default=DEFAULT_DIFFICULTY,
                        help=f"word-length range (default: {DEFAULT_DIFFICULTY})")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Program entry point.  Returns a process exit code."""
    args = parse_args(argv)
    words, note = load_words_with_fallback(args.words)
    if note:
        print(note)
    min_len, max_len = DIFFICULTIES[args.difficulty]
    stats = SessionStats()

    print(f"{LINE}\n  HANGMAN  -  difficulty: {args.difficulty}\n{LINE}")
    try:
        while True:
            try:
                secret = select_word(words, min_len, max_len)
            except ValueError:
                # Word list has nothing in range: use the built-in list.
                secret = select_word(clean_words(FALLBACK_WORDS), min_len, max_len)
            state = play_game(GameState(secret))
            stats.record(state)
            print(render_stats(stats))
            if not ask_replay():
                break
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        return 130
    print("Thanks for playing!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
