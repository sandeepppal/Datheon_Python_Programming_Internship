"""Deterministic unit tests for hangman.py (no network, no real files)."""

import random
import tempfile
import unittest
from pathlib import Path

import hangman
from hangman import GameState, GuessResult


def scripted(inputs):
    """Return an input function that replays ``inputs``."""
    it = iter(inputs)
    return lambda prompt="": next(it)


class WordListTests(unittest.TestCase):
    def test_normalize_valid_and_invalid(self):
        self.assertEqual(hangman.normalize_word("  PyThon \n"), "python")
        for bad in ("", "   ", "don't", "abc1", "caf\u00e9", "two words"):
            self.assertIsNone(hangman.normalize_word(bad), bad)

    def test_clean_words_dedupes_and_filters(self):
        self.assertEqual(hangman.clean_words(["Cat", "cat", "", "d0g", "bird"]),
                         ["cat", "bird"])

    def test_load_words_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.txt"
            path.write_text("apple\nBANANA\n\n123\n", encoding="utf-8")
            self.assertEqual(hangman.load_words(path), ["apple", "banana"])

    def test_missing_file_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            words, note = hangman.load_words_with_fallback(Path(tmp) / "none.txt")
        self.assertTrue(words)
        self.assertIsNotNone(note)

    def test_empty_or_unusable_file_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.txt"
            path.write_text("\n  \n123\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                hangman.load_words(path)
            words, note = hangman.load_words_with_fallback(path)
        self.assertTrue(words)
        self.assertIn("built-in", note)

    def test_invalid_encoding_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.txt"
            path.write_bytes(b"\xff\xfe\x00bad")
            words, note = hangman.load_words_with_fallback(path)
        self.assertTrue(words)
        self.assertIsNotNone(note)

    def test_good_file_gives_no_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.txt"
            path.write_text("alpha\n", encoding="utf-8")
            self.assertEqual(hangman.load_words_with_fallback(path), (["alpha"], None))

    def test_select_word_respects_length_and_seed(self):
        words = ["cat", "horse", "elephant"]
        self.assertEqual(hangman.select_word(words, 5, 5), "horse")
        a = hangman.select_word(words, 3, 8, random.Random(1))
        b = hangman.select_word(words, 3, 8, random.Random(1))
        self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            hangman.select_word(words, 20, 30)

    def test_difficulty_ranges_are_valid(self):
        for low, high in hangman.DIFFICULTIES.values():
            self.assertLessEqual(low, high)

    def test_fallback_words_are_all_valid_and_cover_difficulties(self):
        words = hangman.clean_words(hangman.FALLBACK_WORDS)
        self.assertEqual(len(words), len(set(hangman.FALLBACK_WORDS)))
        for low, high in hangman.DIFFICULTIES.values():
            self.assertTrue(any(low <= len(w) <= high for w in words))


class ValidateGuessTests(unittest.TestCase):
    def test_valid_letters_are_lowercased(self):
        self.assertEqual(hangman.validate_guess("A"), ("a", None))
        self.assertEqual(hangman.validate_guess(" z \n"), ("z", None))

    def test_rejections(self):
        for bad in ("", "   ", "\n", "5", "!", "-", "ab", "hello", "1a", "\u00e9"):
            letter, error = hangman.validate_guess(bad)
            self.assertIsNone(letter, repr(bad))
            self.assertTrue(error, repr(bad))


class GameLogicTests(unittest.TestCase):
    def test_case_insensitive_and_reveals_all_occurrences(self):
        g = GameState("Banana")
        self.assertEqual(g.guess("A"), GuessResult.CORRECT)
        self.assertEqual(g.masked_word(), "_ A _ A _ A")
        self.assertEqual(g.remaining, 6)

    def test_incorrect_guess_costs_exactly_one(self):
        g = GameState("cat")
        self.assertEqual(g.guess("z"), GuessResult.INCORRECT)
        self.assertEqual(g.remaining, 5)
        self.assertEqual(g.wrong_letters, ["z"])

    def test_duplicate_correct_guess_no_penalty(self):
        g = GameState("cat")
        g.guess("c")
        self.assertEqual(g.guess("c"), GuessResult.REPEATED)
        self.assertEqual((g.remaining, g.wrong_count), (6, 0))

    def test_duplicate_incorrect_guess_no_penalty(self):
        g = GameState("cat")
        g.guess("z")
        self.assertEqual(g.guess("z"), GuessResult.REPEATED)
        self.assertEqual(g.remaining, 5)

    def test_victory(self):
        g = GameState("cat")
        for ch in "cat":
            g.guess(ch)
        self.assertTrue(g.is_won)
        self.assertFalse(g.is_lost)
        self.assertTrue(g.is_over)

    def test_defeat_after_exactly_six_wrong(self):
        g = GameState("cat")
        for i, ch in enumerate("bdefgh", start=1):
            g.guess(ch)
            self.assertEqual(g.wrong_count, i)
        self.assertTrue(g.is_lost)
        self.assertEqual(g.remaining, 0)

    def test_five_wrong_is_not_over(self):
        g = GameState("cat")
        for ch in "bdefg":
            g.guess(ch)
        self.assertFalse(g.is_over)
        self.assertEqual(g.remaining, 1)

    def test_win_on_final_attempt_is_a_win(self):
        g = GameState("cat")
        for ch in "bdefg":
            g.guess(ch)
        for ch in "cat":
            g.guess(ch)
        self.assertTrue(g.is_won)
        self.assertFalse(g.is_lost)

    def test_guess_after_game_over_rejected_and_counter_not_negative(self):
        g = GameState("cat")
        for ch in "bdefgh":
            g.guess(ch)
        with self.assertRaises(ValueError):
            g.guess("i")
        self.assertEqual(g.remaining, 0)

    def test_guess_rejects_non_single_letter(self):
        g = GameState("cat")
        for bad in ("", "ab", "1"):
            with self.assertRaises(ValueError):
                g.guess(bad)

    def test_masked_word_hides_unguessed_letters(self):
        self.assertEqual(GameState("cat").masked_word(), "_ _ _")

    def test_new_state_is_independent(self):
        a, b = GameState("cat"), GameState("dog")
        a.guess("c")
        self.assertEqual(b.guessed, set())


class RenderingTests(unittest.TestCase):
    def test_seven_distinct_stages(self):
        self.assertEqual(len(hangman.GALLOWS_STAGES), 7)
        self.assertEqual(len(set(hangman.GALLOWS_STAGES)), 7)

    def test_each_stage_adds_one_part(self):
        parts = ["O", "|", "/", "\\", "/", "\\"]
        stage0 = hangman.GALLOWS_STAGES[0]
        for ch in "O/\\":
            self.assertNotIn(ch, stage0)
        for n in range(1, 7):
            prev = hangman.GALLOWS_STAGES[n - 1]
            cur = hangman.GALLOWS_STAGES[n]
            diff = sum(1 for x, y in zip(prev, cur) if x != y)
            self.assertEqual(diff, 1, f"stage {n}")
            self.assertEqual(cur.count(parts[n - 1]) - prev.count(parts[n - 1]), 1)

    def test_stages_keep_identical_line_widths(self):
        base = [len(line) for line in hangman.GALLOWS_STAGES[0].splitlines()]
        for stage in hangman.GALLOWS_STAGES:
            self.assertEqual([len(line) for line in stage.splitlines()], base)

    def test_board_uses_stage_matching_wrong_count_and_hides_secret(self):
        g = GameState("cat")
        g.guess("z")
        g.guess("y")
        board = hangman.render_board(g)
        self.assertIn(hangman.GALLOWS_STAGES[2], board)
        self.assertIn("4 of 6", board)
        self.assertIn("_ _ _", board)
        self.assertNotIn("CAT", board)

    def test_correct_and_duplicate_guesses_do_not_change_stage(self):
        g = GameState("cat")
        g.guess("c")
        g.guess("c")
        self.assertIn(hangman.GALLOWS_STAGES[0], hangman.render_board(g))

    def test_guessed_letters_sorted(self):
        g = GameState("cat")
        for ch in "zca":
            g.guess(ch)
        self.assertIn("A C Z", hangman.render_board(g))

    def test_end_screens_differ_and_defeat_reveals_word(self):
        g = GameState("cat")
        self.assertIn("CAT", hangman.render_defeat(g))
        self.assertNotEqual(hangman.render_victory(g), hangman.render_defeat(g))

    def test_stats_rendering(self):
        s = hangman.SessionStats(wins=1, losses=1)
        self.assertIn("win rate 50%", hangman.render_stats(s))
        self.assertEqual(hangman.SessionStats().win_rate, 0.0)


class PlayGameTests(unittest.TestCase):
    def run_game(self, secret, inputs):
        out = []
        state = hangman.play_game(GameState(secret), scripted(inputs), out.append)
        return state, "\n".join(out)

    def test_win_flow_with_invalid_and_duplicate_input(self):
        state, out = self.run_game("cat", ["", "1", "ab", "c", "C", "a", "t"])
        self.assertTrue(state.is_won)
        self.assertEqual(state.wrong_count, 0)
        self.assertIn("YOU WIN", out)
        self.assertIn("already guessed", out)
        self.assertIn("Invalid input", out)

    def test_loss_flow_reveals_word(self):
        state, out = self.run_game("cat", list("bdefgh"))
        self.assertTrue(state.is_lost)
        self.assertIn("GAME OVER", out)
        self.assertIn("CAT", out)

    def test_game_ends_immediately_and_ignores_extra_input(self):
        calls = []
        letters = iter("bdefghijk")

        def inp(prompt=""):
            calls.append(prompt)
            return next(letters)

        hangman.play_game(GameState("cat"), inp, lambda s: None)
        self.assertEqual(len(calls), 6)

    def test_secret_not_printed_before_end(self):
        out = []
        it = iter(["z"])

        def inp(prompt=""):
            try:
                return next(it)
            except StopIteration:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            hangman.play_game(GameState("cat"), inp, out.append)
        self.assertNotIn("CAT", "\n".join(out).upper().replace("_", ""))


class ReplayAndMainTests(unittest.TestCase):
    def test_ask_replay(self):
        self.assertTrue(hangman.ask_replay(scripted(["maybe", " YES "])))
        self.assertFalse(hangman.ask_replay(scripted(["n"])))

    def test_stats_record(self):
        s = hangman.SessionStats()
        won = GameState("a")
        won.guess("a")
        lost = GameState("a")
        for ch in "bcdefg":
            lost.guess(ch)
        s.record(won)
        s.record(lost)
        s.record(GameState("a"))  # unfinished: ignored
        self.assertEqual((s.wins, s.losses, s.played), (1, 1, 2))

    def test_parse_args_defaults(self):
        args = hangman.parse_args([])
        self.assertEqual(args.difficulty, "medium")
        self.assertEqual(args.words, hangman.DEFAULT_WORDS_FILE)

    def test_default_path_independent_of_cwd(self):
        self.assertTrue(hangman.DEFAULT_WORDS_FILE.is_absolute())

    def test_main_replay_resets_state(self):
        import builtins
        import contextlib
        import io
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w.txt"
            path.write_text("cart\n", encoding="utf-8")
            # Game 1: win. Replay y. Game 2: lose. Replay n.
            inputs = iter(list("cart") + ["y"] + list("bdefgh") + ["n"])
            buf = io.StringIO()
            with mock.patch.object(builtins, "input", lambda p="": next(inputs)), \
                    contextlib.redirect_stdout(buf):
                code = hangman.main(["--words", str(path), "--difficulty", "easy"])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("2 played, 1 won, 1 lost", out)

    def test_main_handles_ctrl_c_without_traceback(self):
        import builtins
        import contextlib
        import io
        import unittest.mock as mock

        def boom(prompt=""):
            raise KeyboardInterrupt

        buf = io.StringIO()
        with mock.patch.object(builtins, "input", boom), \
                contextlib.redirect_stdout(buf):
            code = hangman.main(["--words", "/nonexistent/words.txt"])
        self.assertEqual(code, 130)
        self.assertIn("Goodbye", buf.getvalue())

    def test_main_handles_eof(self):
        import builtins
        import contextlib
        import io
        import unittest.mock as mock

        def eof(prompt=""):
            raise EOFError

        with mock.patch.object(builtins, "input", eof), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hangman.main(["--words", "/nonexistent"]), 130)


if __name__ == "__main__":
    unittest.main()
