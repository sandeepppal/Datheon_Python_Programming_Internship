# Hangman Word Guessing Game

A console Hangman game written in Python, built for the **Datheon Python
Programming Internship** task. It uses only the Python standard library.

## Features

**Required by the task**
- Executable console app `hangman.py`, hidden word guessed one letter at a time
- Maximum of six incorrect guesses
- ASCII gallows with seven stages (0-6 incorrect guesses)
- Tracking of guessed letters; duplicate guesses never cost an attempt
- Masked word display, e.g. `_ A _ H E O N`
- Distinct victory and defeat screens
- Modular code using string manipulation and control flow

**Optional (kept small on purpose)**
- Three difficulty levels (word-length ranges)
- Replay loop with session statistics (played / won / lost / win rate)
- Offline fallback word list if `words.txt` is missing or unusable
- Graceful Ctrl+C / Ctrl+D handling

Not implemented: persistent JSON leaderboard and colour output. They add failure
modes (corrupt files, terminal compatibility) without helping the core
requirements. See *Future improvements*.

## Requirements

- Python 3.9 or newer (developed and tested on 3.12)
- No third-party packages (`requirements.txt` is not needed)

## Files

```
hangman.py        Game: word loading, logic, rendering, main loop
fetch_words.py    Explicit, one-off downloader for words.txt
test_hangman.py   unittest suite (offline, deterministic)
README.md
.gitignore
words.txt         Created by you with fetch_words.py (git-ignored)
```

## Word-list setup

The game never touches the network. To use the full word list, run once:

```
python fetch_words.py
```

This saves the list to `words.txt` next to `hangman.py`. If you are offline,
download the file manually from the URL below and save it as `words.txt` (UTF-8,
one word per line).

If `words.txt` is missing, empty, or not valid UTF-8, the game prints a note and
uses a small built-in list, so it always runs.

Loaded entries are stripped, lower-cased, de-duplicated, and kept only if they
are ASCII letters.

## Run

```
python hangman.py
python hangman.py --difficulty easy      # easy | medium | hard
python hangman.py --words path/to/list.txt
```

| Difficulty | Word length |
|------------|-------------|
| easy       | 4-6         |
| medium (default) | 5-8   |
| hard       | 8-14        |

## Test

```
python -m unittest -v
```

Tests use temporary files and scripted input, so they do not need the network
and never touch your real `words.txt`.

## Rules and controls

- Type one letter (A-Z, any case) and press Enter.
- A correct letter reveals every occurrence in the word.
- A new wrong letter costs one of six attempts.
- Repeating a letter (right or wrong) shows a message and costs nothing.
- Empty input, digits, symbols, or more than one character are rejected.
- Win by revealing the whole word; lose after six wrong guesses (the word is
  then revealed).
- After each game you are asked whether to play again.

## Example session

```
============================================
  +---+
  |   |
      |
      |
      |
      |
=========

  Word:       _ _ _ _ _ _
  Attempts:   6 of 6 remaining
  Guessed:    (none)
  Incorrect:  (none)
============================================
Guess a letter: e
Good guess! 'E' is in the word.
```

## Design decisions

- **One game module plus tests.** The project is small, so splitting into many
  files would add navigation cost without clarity. Inside `hangman.py`,
  responsibilities are separated into functions: loading/validation,
  `validate_guess`, `GameState`, `render_*`, and `play_game`/`main`.
- **`GameState` is a small dataclass.** The only stored state is the secret and
  the set of guessed letters. Wrong guesses, remaining attempts, win and loss are
  *derived* from that set, so they cannot get out of sync, and the counter can
  never go negative.
- **Injectable I/O.** `play_game` takes input and output functions, so whole
  games are tested without a keyboard.
- **Validation is separate from logic.** `validate_guess` cleans input;
  `GameState.guess` still refuses invalid letters.
- **Conservative fallback.** Missing or bad data never crashes the game.
- **No broad `except Exception`.** Only specific expected errors are caught.

## Known limitations

- English ASCII letters only (no accents).
- The word list is the most frequent English words, so some are very common or
  abbreviations. Difficulty is based on length only, not on how obscure a word is.
- Statistics last for one run of the program only.
- Assumes a terminal with a monospaced font.

## Data source and licence

Word list: `google-10000-english-no-swears.txt` from the
`first20hours/google-10000-english` repository:
https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt

The list is **not** included in this repository. Before redistributing it,
check the repository's licence page and the original data-source notes yourself;
I have not verified the terms here. Fetching it locally for personal use through
`fetch_words.py` does not redistribute it.

## Future improvements

- Optional JSON statistics file with safe handling of malformed or unwritable files
- Optional colour output with a plain-text fallback
- Difficulty based on letter rarity as well as length
