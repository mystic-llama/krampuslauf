"""Run with: python -m unittest -v test_fantasy_name_generator"""

from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fantasy_name_generator as names


class FantasyNameTests(unittest.TestCase):
    def tiny(self, **kwargs):
        return names.FantasyNameGenerator(
            first_names=("Arin", "Mira", "Vale"), surnames=("Vale", "Wren"),
            seed=12, **kwargs)

    def test_validation_includes_the_space(self):
        self.assertEqual(names.validate_name("Alara Silverleaf"), "Alara Silverleaf")
        self.assertTrue(names.is_valid_name("A" * 16))
        self.assertTrue(names.is_valid_name("Alar Silverleafs"))
        self.assertFalse(names.is_valid_name("Alara SilverleafsX"))
        self.assertTrue(names.is_valid_name("Arin Vale", 9))
        self.assertFalse(names.is_valid_name("Arin Vale", 8))

    def test_digits_punctuation_unicode_and_bad_spacing_are_rejected(self):
        bad = ("Arin2", "Arin Vale2", "123", "Arin-Vale", "Arin'Vale", "Arin_Vale",
               " Arin", "Arin ", "Arin  Vale", "Arin\tVale", "Arin\nVale", "Arin\n",
               "Arin Vale Wren", "\u00c1rin", "Arin\u00a0Vale", "", "A", None, 24)
        for candidate in bad:
            with self.subTest(candidate=candidate):
                self.assertFalse(names.is_valid_name(candidate))

    def test_bad_limits_and_counts_are_rejected(self):
        generator = self.tiny()
        for limit in (1, 0, -1, 17, 99, True, 16.0, "16", None):
            with self.assertRaises(ValueError):
                generator.generate(max_length=limit)
        for count in (-1, True, 1.0, "1", None):
            with self.assertRaises(ValueError):
                generator.generate_many(count)
        with self.assertRaises(ValueError):
            generator.generate(style="samurai")
        self.assertEqual(generator.used_names, set())

    def test_all_dictionary_names_have_valid_format(self):
        self.assertGreater(len(names.FIRST_NAMES), 8000)
        self.assertGreater(len(names.SURNAMES), 400)
        for pool in (names.FIRST_NAMES, names.SURNAMES):
            self.assertEqual(len(pool), len({n.lower() for n in pool}))
            self.assertTrue(all(names.is_valid_name(n) and " " not in n for n in pool))

    def test_large_batch_is_valid_and_unique(self):
        generator = names.FantasyNameGenerator(seed=42)
        generated = generator.generate_many(25000, style="mixed")
        self.assertEqual(len(generated), len({n.lower() for n in generated}))
        self.assertTrue(all(names.is_valid_name(n) for n in generated))
        self.assertEqual(len(generator.used_names), 25000)

    def test_styles_and_shorter_limits(self):
        for style in names.STYLES:
            generator = names.FantasyNameGenerator(seed=4)
            generated = generator.generate_many(100, style=style, max_length=10)
            self.assertTrue(all(names.is_valid_name(n, 10) for n in generated))
            if style == "single":
                self.assertTrue(all(" " not in n for n in generated))
            elif style == "full":
                self.assertTrue(all(n.count(" ") == 1 for n in generated))

    def test_mixed_style_uses_both_formats(self):
        generated = names.FantasyNameGenerator(seed=87).generate_many(1000)
        full_count = sum(" " in n for n in generated)
        self.assertGreater(full_count, 350)
        self.assertLess(full_count, 650)

    def test_independent_seeded_instances_repeat_preview_sequence(self):
        a = names.FantasyNameGenerator(seed=42).generate_many(100)
        b = names.FantasyNameGenerator(seed=42).generate_many(100)
        self.assertEqual(a, b)

    def test_uniqueness_across_calls_and_styles(self):
        generator = self.tiny()
        first = generator.generate_many(2, style="single")
        rest = generator.generate_many(generator.remaining(), style="mixed")
        combined = first + rest
        self.assertEqual(len(combined), len(set(combined)))
        self.assertEqual(generator.remaining(), 0)

    def test_case_and_whitespace_normalization(self):
        generator = self.tiny(used_names=["  ARIN   VALE ", "mira WREN"])
        generator.reserve(["arin vale", " MIRA "])
        self.assertEqual(generator.used_names, {"arin vale", "mira wren", "mira"})
        generated = generator.generate_many(generator.remaining())
        self.assertNotIn("Arin Vale", generated)
        self.assertNotIn("Mira Wren", generated)
        self.assertNotIn("Mira", generated)

    def test_exact_capacity_and_indexing_against_cartesian_product(self):
        for limit, style in itertools.product(range(2, 17), names.STYLES):
            generator = self.tiny()
            single = {n for n in ("Arin", "Mira", "Vale") if len(n) <= limit}
            full = {first + " " + last
                    for first, last in itertools.product(
                        ("Arin", "Mira", "Vale"), ("Vale", "Wren"))
                    if first != last and len(first + " " + last) <= limit}
            expected = single if style == "single" else full if style == "full" else single | full
            self.assertEqual(generator.remaining(style, limit), len(expected))
            actual = generator.generate_many(len(expected), style, limit)
            self.assertEqual(set(actual), expected)
            self.assertEqual(generator.remaining(style, limit), 0)

    def test_blocked_fragments_are_removed_from_words_and_across_the_space(self):
        generator = names.FantasyNameGenerator(
            first_names=("Shitha", "Shi", "Arin", "Cassia"),
            surnames=("Rowan", "Tha", "Pissarro"),
            used_names=["Shitha Rowan", "Shi Tha"])
        expected = {"Shi Rowan", "Arin Rowan", "Arin Tha"}
        self.assertEqual(generator.remaining("full"), len(expected))
        self.assertFalse(generator.matches("sHItHa RoWaN"))
        self.assertFalse(generator.matches("sHI tHA"))
        self.assertEqual(set(generator.generate_many(len(expected), "full")), expected)
        self.assertEqual(generator.remaining("full"), 0)
        self.assertEqual(set(generator.generate_many(2, "single")), {"Shi", "Arin"})

    def test_exhausted_pool_never_falls_back_to_digits_or_duplicates(self):
        generator = self.tiny()
        generator.generate_many(generator.remaining())
        old_history = generator.used_names
        with self.assertRaises(names.NamePoolExhausted):
            generator.generate()
        self.assertEqual(generator.used_names, old_history)

    def test_impossible_batch_does_not_reserve_partial_results(self):
        generator = self.tiny()
        with self.assertRaises(names.NamePoolExhausted):
            generator.generate_many(generator.remaining() + 1)
        self.assertEqual(generator.used_names, set())

    def test_near_exhaustion_fallback_finds_only_remaining_name(self):
        generator = self.tiny(used_names=["Arin", "Mira"])
        with patch.object(generator._rng, "randrange", return_value=0):
            self.assertEqual(generator.generate("single"), "Vale")

    def test_empty_pool_and_no_full_name_that_fits(self):
        generator = names.FantasyNameGenerator(first_names=(), surnames=())
        self.assertEqual(generator.remaining(), 0)
        with self.assertRaises(names.NamePoolExhausted):
            generator.generate()
        generator = names.FantasyNameGenerator(first_names=("Arin",), surnames=())
        self.assertEqual(generator.generate(), "Arin")
        with self.assertRaises(names.NamePoolExhausted):
            self.tiny().generate("full", max_length=8)

    def test_history_remembers_names_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "subfolder" / "names.json"
            a = self.tiny(history_path=history)
            first = a.generate_many(3)
            b = self.tiny(history_path=history)
            self.assertEqual(b.used_names, {n.lower() for n in first})
            second = b.generate_many(b.remaining())
            self.assertFalse(set(first) & set(second))
            with history.open(encoding="utf-8") as handle:
                stored = json.load(handle)
            self.assertEqual(stored["version"], 1)
            self.assertEqual(set(stored["names"]), b.used_names)

    def test_history_reserve_and_zero_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.json"
            generator = self.tiny(history_path=path)
            self.assertEqual(generator.generate_many(0), [])
            self.assertFalse(path.exists())
            generator.reserve(["Arin Vale"])
            self.assertIn("arin vale", self.tiny(history_path=path).used_names)

    def test_invalid_history_does_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.json"
            for text in ("{broken", "[]", '{"version": 2, "names": []}',
                         '{"version": 1, "names": ["Arin2"]}'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(names.NameHistoryError):
                    self.tiny(history_path=path)
                self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_save_failure_preserves_old_file_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.json"
            generator = self.tiny(history_path=path)
            generator.reserve(["Arin"])
            before = path.read_bytes()
            with patch.object(names.os, "replace", side_effect=PermissionError("test failure")):
                with self.assertRaises(names.NameHistoryError):
                    generator.generate_many(2)
            self.assertEqual(generator.used_names, {"arin"})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_history_copy_cannot_mutate_generator(self):
        generator = self.tiny(used_names=["Arin"])
        snapshot = generator.used_names
        snapshot.clear()
        self.assertEqual(generator.used_names, {"arin"})

    def test_custom_dictionary_and_reserved_input_validation(self):
        generator = names.FantasyNameGenerator(
            first_names=("ARIN", "Arin", "Mira"), surnames=("VALE", "Vale"))
        self.assertEqual(generator.remaining(), 4)
        for invalid in (["A2"], ["Arin Vale"], "Arin"):
            with self.assertRaises(ValueError):
                names.FantasyNameGenerator(first_names=invalid)
        with self.assertRaises(ValueError):
            generator.reserve("Arin Vale")
        with self.assertRaises(ValueError):
            generator.reserve(["Arin", "Mira2"])
        self.assertEqual(generator.used_names, set())

    def test_one_shared_instance_is_thread_safe(self):
        generator = names.FantasyNameGenerator(seed=7)
        with ThreadPoolExecutor(max_workers=4) as executor:
            batches = list(executor.map(lambda _: generator.generate_many(100), range(8)))
        all_names = [name for batch in batches for name in batch]
        self.assertEqual(len(all_names), len(set(all_names)))
        self.assertEqual(len(generator.used_names), 800)

    def test_cli_json_and_invalid_options(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = names.main(["--count", "8", "--style", "full", "--seed", "4", "--json"])
        generated = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(len(generated), 8)
        self.assertTrue(all(names.is_valid_name(n) and " " in n for n in generated))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                names.main(["--max-length", "17"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()


def test_all_category_styles_share_duplicate_history(tmp_path):
    path = tmp_path / 'names.json'
    generator = names.FantasyNameGenerator(seed=42, history_path=path)
    results = []
    for category in names.CATEGORIES:
        for style in names.STYLES:
            batch = generator.generate_many(50, style=style, category=category)
            assert all(names.is_valid_name(n) for n in batch)
            if category.startswith('gargoyle'):
                assert all(' ' not in n for n in batch)
            results.extend(batch)
    assert len(results) == len({n.casefold() for n in results})
    assert names.FantasyNameGenerator(history_path=path).used_names == generator.used_names


def test_gargoyle_single_name_pools_remain_as_large_as_other_races():
    generator = names.FantasyNameGenerator()
    for sex, minimum in (('male', 5496), ('female', 3381)):
        gargoyle = generator.remaining('single', category='gargoyle_' + sex)
        assert gargoyle >= minimum
        assert gargoyle >= generator.remaining('single', category='human_' + sex)
        assert gargoyle >= generator.remaining('single', category='elf_' + sex)
