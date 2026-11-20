#!/usr/bin/env python3
"""Pronounceable fantasy names for Krampuslauf. Version 1.0.0.

Python 3.8+; standard library only. Importing this file does not read or write
files, print anything, or interact with the game.

    from fantasy_name_generator import FantasyNameGenerator
    names = FantasyNameGenerator(history_path="used_character_names.json")
    character_name = names.generate(style="mixed")

Keep ONE generator instance for the application. An optional JSON history
remembers names across restarts. Format validation is local; the game can have
additional naming restrictions. No character classes or gender categories.
"""

import argparse
from bisect import bisect_right
import json
import os
from pathlib import Path
import random
import re
import tempfile
import threading

__version__ = "1.0.0"
MAX_NAME_LENGTH = 16
STYLES = ("single", "full", "mixed")


# ============================================================================
# EDITABLE NAME DICTIONARY
# Add space-separated words inside the triple quotes. Use letters A-Z only.
# FIRST_SYLLABLES end in a vowel; LAST_SYLLABLES start with a consonant.
# Joining complete syllables makes smoother names than random letter strings.
# SURNAMES are deliberately hand-selected, rather than arbitrary word pairs.
# ============================================================================

CURATED_FIRST_NAMES = tuple("""
Aelar Aelin Aerin Aethan Aila Aira Alara Alden Aldric Alina Alira Alora
Alric Amara Amaris Anara Anwen Arden Aric Arin Arlen Arlis Arlo Arlyn
Arven Asha Aster Astra Auren Auron Avan Aven Avira Ayla Azra Baelen
Baerin Balen Belan Belara Belen Belira Beren Berin Beron Bira Borin
Braen Bran Bren Brenna Brina Brin Bryn Caelan Caelin Caera Cailen Calan
Calen Calia Calin Calla Calren Caris Carys Cavan Cedran Celes Celia Celyn
Cera Cerin Cerys Coran Coren Corin Corra Cyra Dain Dalen Dalia Dara
Daren Darian Darin Darya Davan Delan Delia Delin Delyn Dena Doran Doria
Dorin Dren Dwyn Eira Eiren Elan Elara Eldan Elden Eldric Elena Elin
Elira Elora Elowen Elric Elyra Emara Emera Emery Emrys Enara Eren Erian
Eris Erin Eryn Esra Esten Evara Evren Faelan Faelin Faera Falen Fara
Faren Farin Faye Fen Fenna Fennel Fera Ferin Fia Fira Fola Galan Galen
Galia Galin Gara Garen Garran Gera Gethan Gila Goran Goria Grena Gwen
Haelan Halen Halia Halin Halra Hara Haren Harin Helan Hela Hira Hollis
Ilan Ilara Ilia Ilian Ilira Ilora Inara Iona Iora Ira Iren Iria Iriel
Isen Isla Isora Ivara Jalen Jara Jaren Jarin Jora Joren Joria Jorin
Kael Kaela Kaelen Kalen Kalia Kalin Kara Karenna Karia Karys Kavan
Kelia Kelin Kelra Kera Keren Kestrel Kira Kora Koren Korin Kyra Laela
Laen Laila Lain Laira Lalen Lara Laren Laria Larin Lark Lelan Lelia
Lenna Leora Lera Lerin Liana Lira Liren Liria Lirien Lora Loren Loria
Lorin Lorna Lura Lyran Lyra Maela Maelin Maera Malan Malen Malia Malin
Mara Maren Maria Mariel Marin Maris Mave Mela Melan Melia Melin Mera
Merin Merrin Mira Miran Miren Miri Moren Moria Morin Myra Naela Naerin
Nalen Nalia Nalin Nara Naren Naria Narin Nella Nera Nerin Nessa Nevara
Nia Nila Nira Niva Nivara Nola Nora Noren Noria Norin Nyra Olan Olara
Olen Olia Olira Olwen Ora Oren Oria Oriel Orin Orla Orlen Orlyn Oryn
Ovara Paela Palen Palia Pella Pera Perin Perrin Petra Pira Pyria Raela
Raelin Raen Raena Raera Ralen Ralia Ralin Rava Ravel Ravia Ravin Rela
Relan Relia Relin Rena Renen Ria Rian Riel Rila Rilen Rina Risa Riva
Riven Roan Rolan Rolen Rona Ronan Rora Rorin Rowan Runa Rylen Saela
Saelin Saera Salan Salen Salia Salin Samara Sana Saren Saria Sarin
Sava Selan Sela Selen Selia Selin Senna Sera Seren Serin Shae Shara
Shayla Shira Silas Silen Sira Sola Solan Solen Sora Soren Sorin Sylas
Sylva Syra Taela Taelin Taera Talen Talia Talin Talora Tamara Tana
Taren Taria Tarin Tava Telan Telia Telin Tera Teren Terin Thalen Thalia
Thalin Thara Tharen Tharin Thea Thelan Therin Thora Thoren Thorin Tia
Tira Tirin Toran Toren Toria Torin Trena Tyla Tyra Vaela Vaelin Vaera
Valan Valen Valia Valin Valora Vana Vara Varen Varia Varin Vela Velen
Velia Velin Venna Vera Veren Verin Veya Via Vian Vira Viren Viria Vora
Voren Vorin Vyla Vyra Walen Walia Wara Wela Welin Willa Wren Wyla
Wynna Xaela Xara Xela Xira Yaela Yalen Yara Yaren Yela Yelin Yena Yira
Yora Yoren Yria Zaela Zaelin Zaera Zalen Zalia Zalin Zara Zaren Zaria
Zarin Zela Zelen Zelia Zelin Zena Zera Zerin Zia Zira Ziren Zora Zoren
Zoria Zorin Zyla Zyra
""".split())

FIRST_SYLLABLES = tuple("""
Ae Ala Ale Ali Ari Ava Bela Beli Bora Ca Cala Celi Da Dara Dela
Ela Eli Eri Fa Fae Fara Feli Gala Gara Ha Hala Ila Iri Jara Jora
Ka Kala Kara Keli La Lara Liri Lora Ma Mara Meli Mira Na Nara
Nera Nori Ola Ori Pela Pera Ra Rava Rena Ria Riva Rona Sa Sara
Sela Sera Sha Shala Shi Sora Ta Tala Tara Teli Thala Thara Thea
Thora Tira Tyra Va Vala Vara Vela Vera Vira Wila Yara Yela Zala
Zara Zela Zira
""".split())

LAST_SYLLABLES = tuple("""
ban bel bor dan dar den din dor dra drel drin dros fal fan fel fin
gan gar gen gin han har hen hin ka kan kar kel kin kor la lan lar
len lia lin lis lon lor lyn ma mar mel min mir mon na nar nel nia
nin nis nor nys ra ral ran rel ren ria riel rin ris ron ryn sa sar
sel sen sha sin sor ta tal tan tar tel ten thas thel thin thir thor
tis tor va val van var vel ven via vin vor vyn wyn ya yel yen
""".split())

SURNAMES = tuple("""
Alder Arden Arlow Aster Birch Briar Bracken Brook Calder Cinder Corven
Dale Darrow Dusk Elden Elmont Ember Evern Fallow Farrow Fenn Fern Fell
Flint Frost Glen Gloam Grey Hale Hart Hawke Hazel Hollin Hollow Ivy
Lark Laurel Leaf Lorne Lowen Lynden Mallow Marsh Mere Mist Moon Moss
Oak Onyx Pine Quill Rain Raven Reed Rill River Rook Rose Rowan Rune
Sable Shade Shaw Silver Snow Solis Star Steele Stone Storm Tarn Thorne
Vale Vesper Warden Wells West Wild Willow Wind Winter Wolf Wren Yarrow
Yew Amberfall Amberwick Ashbrook Ashenvale Ashford Ashgrove Ashmere
Ashwood Autumnvale Birchfall Birchwood Blackthorn Brightbrook Brightvale
Brightwood Briarfall Briarwood Brookdale Brookfell Brookhaven Brookmere
Cloudfall Cloudmere Cloudsong Cloudvale Copperleaf Copperwood Crowmere
Dawnfall Dawnglade Dawnmere Dawnsong Dawnvale Dawnsward Deepbrook
Deepgrove Deepmere Deepwood Dewfall Dewglade Dreamvale Duskmere Duskrill
Duskvale Duskwood Emberfall Emberglade Embermere Embervale Emberwood
Everbrook Everglade Everleaf Evermere Everwood Fairbrook Fairglade
Fairmere Fairvale Fairwind Farbrook Farglen Farhaven Farmere Fernbrook
Ferndale Fernglen Fernhill Fernmere Fernvale Flintbrook Flintdale
Flintmere Flintvale Foxglade Foxgrove Foxmere Foxvale Frostbloom
Frostbrook Frostfall Frostfern Frostglen Frostmere Frostvale Frostwood
Glenbrook Glendell Glenmere Goldleaf Goldmere Goldenvale Greenbriar
Greenbrook Greenglen Greenleaf Greenmere Greenvale Greenwillow Greybrook
Greyfall Greyfen Greyhaven Greyhill Greymere Greyvale Greywind Greywood
Hawthorne Hazelbrook Hazelglen Hazelwood Highbrook Highglen Highmere
Highvale Hillbrook Hillcrest Hillmere Hollowbrook Hollowglen Hollowmere
Hollowvale Ironbark Ironbrook Ironleaf Ironmere Ironvale Ironwood
Ivybrook Ivyglen Ivyhollow Ivyvale Jadewood Larkbrook Larkglen Larkspur
Larkvale Leafbrook Leafmere Leafsong Lightbrook Lightfall Lightmere
Lightvale Longbrook Longmere Lowbrook Lowglen Marshbrook Marshglen
Marshmere Meadowbrook Meadowglen Meadowmere Mistbrook Mistfall Mistfern
Mistglen Mistmere Mistvale Mistwood Moonbloom Moonbrook Moonfall
Moonfern Moonglade Moonleaf Moonmere Moonsong Moonvale Moonweave
Mossbrook Mossdale Mossglen Mosshollow Mossmere Mossvale Nightbloom
Nightbrook Nightfall Nightfern Nightmere Nightsong Nightvale Oakbrook
Oakdale Oakfell Oakglen Oakhaven Oakhill Oakmere Oakvale Pinebrook
Pinedale Pinefell Pineglen Pinemere Pinevale Quillbrook Quillmere
Rainbrook Rainfall Rainfern Rainglen Rainmere Rainsong Rainvale
Ravenbrook Ravenfell Ravenglen Ravenmere Ravenvale Redbrook Redfern
Redglen Redleaf Redmere Redvale Reedbrook Reedglen Reedmere Reedvale
Ridgebrook Rillbrook Rillmere Riverbloom Riverdale Riverglen Riverleaf
Rivermere Riversong Rivervale Rookbrook Rookfell Rookmere Rosebrook
Roseglen Roseleaf Rosemere Rosevale Rosewood Runebrook Runefall
Runeglen Runeleaf Runemere Runesong Runevale Runeweave Sablebrook
Sableglen Sablemere Sablevale Shadebrook Shadefern Shadeglen Shademere
Shadevale Shadewood Silverash Silverbloom Silverbrook Silverfern
Silverglen Silverleaf Silvermere Silvervale Silverwood Skybloom
Skybrook Skyfall Skyfern Skyglen Skymere Skysong Skyvale Snowbloom
Snowbrook Snowfall Snowfern Snowglen Snowmere Snowvale Starbloom
Starbrook Starfall Starfern Starglen Starleaf Starmere Starsong
Starvale Starweave Stillbrook Stillglen Stillmere Stonebrook Stonedale
Stonefell Stoneglen Stonehaven Stonehill Stonemere Stonevale Stormbloom
Stormbrook Stormfall Stormfern Stormglen Stormmere Stormsong Stormvale
Sunbloom Sunbrook Sunfall Sunfern Sunglade Sunglen Sunleaf Sunmere
Sunsong Sunvale Thornbrook Thorndale Thornfell Thornglen Thornmere
Thornvale Valebrook Valefall Valemere Valeweave Westbrook Westfall
Westfern Westglen Westmere Westvale Wildbloom Wildbrook Wildfern
Wildglen Wildmere Wildrose Wildvale Wildwood Willowbrook Willowglen
Willowmere Willowvale Windbloom Windbrook Windfall Windfern Windglen
Windmere Windsong Windvale Winterbloom Winterbrook Winterfern
Winterglen Wintermere Wintervale Wispbrook Wispglen Wispmere Wispvale
Wolfbrook Wolffell Wolfglen Wolfmere Wolfvale Woodbrook Woodfern
Woodglen Woodmere Woodvale Wrenbrook Wrenglen Wrenmere Wrenvale
""".split())

# ============================================================================
# GENERATOR ENGINE -- the dictionary above is the normal customization area.
# ============================================================================


class NamePoolExhausted(ValueError):
    """The requested number exceeds the remaining valid, unused names."""


class NameHistoryError(RuntimeError):
    """History could not be read or safely saved; it was not silently reset."""


def _length_limit(max_length):
    if isinstance(max_length, bool) or not isinstance(max_length, int):
        raise ValueError("max_length must be an integer from 2 through 16.")
    if not 2 <= max_length <= MAX_NAME_LENGTH:
        raise ValueError("max_length must be from 2 through 16.")
    return max_length


def validate_name(name, max_length=MAX_NAME_LENGTH):
    """Return name unchanged, or raise ValueError with a readable reason.

    Accepts one or two words containing only ASCII letters, with exactly one
    space between words. Length includes that space. Does not trim or truncate.
    """
    _length_limit(max_length)
    if not isinstance(name, str):
        raise ValueError("A name must be text.")
    if not 2 <= len(name) <= max_length:
        raise ValueError("A name must contain 2 to %d characters, including spaces."
                         % max_length)
    if re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)?", name) is None:
        raise ValueError("Use letters A-Z only, with one optional space between "
                         "first and last names; no digits or punctuation.")
    return name


def is_valid_name(name, max_length=MAX_NAME_LENGTH):
    """Boolean form of validate_name; an invalid limit also returns False."""
    try:
        validate_name(name, max_length)
        return True
    except ValueError:
        return False


def _unique_words(words, label):
    if isinstance(words, str):
        raise ValueError("%s must be a sequence of words, not one string." % label)
    seen = set()
    result = []
    for word in words:
        validate_name(word)
        if " " in word:
            raise ValueError("Each %s entry must be a single word." % label)
        key = word.lower()
        if key not in seen:
            seen.add(key)
            result.append(word[0].upper() + word[1:].lower())
    return tuple(result)


def _build_first_names():
    for syllable in FIRST_SYLLABLES:
        if not syllable.isascii() or not syllable.isalpha() or \
                syllable[-1].lower() not in "aeiou":
            raise ValueError("First syllables must be letters ending in a vowel.")
    for syllable in LAST_SYLLABLES:
        if not syllable.isascii() or not syllable.isalpha() or \
                syllable[0].lower() in "aeiou":
            raise ValueError("Last syllables must start with a consonant.")
    made = []
    for first in FIRST_SYLLABLES:
        for last in LAST_SYLLABLES:
            word = first + last
            # Avoid obvious echoes such as Lalala, while keeping real syllables.
            if first.lower().endswith(last.lower()) or \
                    last.lower().startswith(first.lower()):
                continue
            if 3 <= len(word) <= 10:
                made.append(word)
    return _unique_words(CURATED_FIRST_NAMES + tuple(made), "first names")


FIRST_NAMES = _build_first_names()
SURNAMES = _unique_words(SURNAMES, "surnames")


def _name_key(name):
    if not isinstance(name, str):
        raise ValueError("History entries must be text.")
    canonical = " ".join(name.split())
    validate_name(canonical)
    return canonical.lower()


def _name_keys(names):
    if isinstance(names, str):
        raise ValueError("Pass a collection of names, for example ['Arin Vale'].")
    return {_name_key(name) for name in names}


class _NameSpace:
    """Indexed finite name space, without allocating every full-name string."""

    def __init__(self, first_names, surnames, style, max_length):
        self.style = style
        self.max_length = max_length
        self.first_names = tuple(n for n in first_names if len(n) <= max_length)
        self.first_keys = {n.lower() for n in self.first_names}
        self.surname_keys = {n.lower() for n in surnames}
        self.rows = []
        self.ends = []
        self.size = len(self.first_names) if style == "single" else 0
        if style == "full":
            by_budget = {}
            for first in self.first_names:
                budget = max_length - len(first) - 1
                if budget not in by_budget:
                    by_budget[budget] = tuple(s for s in surnames if len(s) <= budget)
                choices = by_budget[budget]
                if first.lower() in self.surname_keys:
                    choices = tuple(s for s in choices if s.lower() != first.lower())
                if choices:
                    self.rows.append((first, choices))
                    self.size += len(choices)
                    self.ends.append(self.size)

    def at(self, index):
        if self.style == "single":
            return self.first_names[index]
        row = bisect_right(self.ends, index)
        start = self.ends[row - 1] if row else 0
        first, choices = self.rows[row]
        return first + " " + choices[index - start]

    def contains(self, key):
        if len(key) > self.max_length:
            return False
        parts = key.split(" ")
        if self.style == "single":
            return len(parts) == 1 and key in self.first_keys
        return (len(parts) == 2 and parts[0] in self.first_keys and
                parts[1] in self.surname_keys and parts[0] != parts[1])


from fantasy_name_libraries import NAME_LIBRARIES

CATEGORIES = tuple(NAME_LIBRARIES)


class FantasyNameGenerator:
    """Session-unique names, with optional persistent JSON duplicate history.

    style='single': one given name.
    style='full': first and last name, including the space in the length limit.
    style='mixed': equal chance of either style while both have unused names.

    All successful generated names are reserved immediately, even if the host
    application later cancels character creation. This prevents accidental reuse.
    One instance is safe to share between application threads. A history file
    must have one owning instance/process; it is not a shared database.
    """

    def __init__(self, seed=None, history_path=None, used_names=None,
                 first_names=None, surnames=None):
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self._first_names = _unique_words(
            FIRST_NAMES if first_names is None else first_names, "first names")
        self._surnames = _unique_words(
            SURNAMES if surnames is None else surnames, "surnames")
        self._spaces = {}
        self._history_path = Path(history_path) if history_path is not None else None
        self._used = self._load_history()
        if used_names is not None:
            self._used.update(_name_keys(used_names))

    @property
    def used_names(self):
        """A copy of the case-insensitive duplicate keys; safe to serialize."""
        with self._lock:
            return set(self._used)

    def _load_history(self):
        if self._history_path is None:
            return set()
        try:
            with self._history_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return set()
        except (OSError, ValueError) as exc:
            raise NameHistoryError("Cannot read name history: %s" % exc) from exc
        try:
            if not isinstance(payload, dict) or payload.get("version") != 1 or \
                    not isinstance(payload.get("names"), list):
                raise ValueError("Expected a version 1 history object with a names list.")
            return _name_keys(payload["names"])
        except ValueError as exc:
            raise NameHistoryError("Invalid name history: %s" % exc) from exc

    def _save_history(self, used):
        if self._history_path is None:
            return
        temp_path = None
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=str(self._history_path.parent),
                    prefix="." + self._history_path.name + ".", suffix=".tmp",
                    delete=False) as handle:
                temp_path = handle.name
                json.dump({"version": 1, "names": sorted(used)}, handle,
                          indent=2, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._history_path)
        except OSError as exc:
            raise NameHistoryError("Cannot save name history: %s" % exc) from exc
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def reserve(self, names):
        """Reserve existing names or rejected attempts; persist if configured.

        Case and repeated whitespace are normalized for duplicate comparisons.
        Existing names need not be in this generator's dictionary.
        """
        additions = _name_keys(names)
        with self._lock:
            combined = self._used | additions
            self._save_history(combined)
            self._used = combined

    def _get_spaces(self, style, max_length, category=None):
        _length_limit(max_length)
        if style not in STYLES:
            raise ValueError("style must be 'single', 'full', or 'mixed'.")
        first, surnames = self._first_names, self._surnames
        if category is not None:
            if category not in NAME_LIBRARIES:
                raise ValueError("Unknown name category: %s" % category)
            library = NAME_LIBRARIES[category]
            first = _unique_words(library['curated'] + [a + b for a in library['first_syll']
                                  for b in library['last_syll']], 'first names')
            surnames = tuple(library['surnames'])
        requested = ("single", "full") if style == "mixed" else (style,)
        # Gargoyle libraries intentionally have no surnames.
        if category is not None and not surnames:
            requested = ("single",)
        result = []
        for kind in requested:
            key = (category, kind, max_length)
            if key not in self._spaces:
                self._spaces[key] = _NameSpace(
                    first, surnames, kind, max_length)
            result.append(self._spaces[key])
        return result

    def remaining(self, style="mixed", max_length=MAX_NAME_LENGTH, category=None):
        """Exact number of names still available for this style and limit."""
        with self._lock:
            spaces = self._get_spaces(style, max_length, category)
            return sum(space.size - sum(space.contains(n) for n in self._used)
                       for space in spaces)

    def _choose_unused(self, space, used):
        # Fast for ordinary use; the exhaustive fallback guarantees termination
        # and success when even one valid name remains in a nearly empty pool.
        for _ in range(64):
            name = space.at(self._rng.randrange(space.size))
            if name.lower() not in used:
                return name
        start = self._rng.randrange(space.size)
        for offset in range(space.size):
            name = space.at((start + offset) % space.size)
            if name.lower() not in used:
                return name
        raise NamePoolExhausted("No unused names remain in this name pool.")

    def generate(self, style="mixed", max_length=MAX_NAME_LENGTH, category=None):
        """Generate and remember one name. No digits or truncation fallbacks."""
        return self.generate_many(1, style=style, max_length=max_length, category=category)[0]

    def generate_many(self, count, style="mixed", max_length=MAX_NAME_LENGTH, category=None):
        """Generate a unique batch. An impossible request reserves no names.

        History is saved once per batch, before the names are returned. Failure
        to save raises NameHistoryError and leaves in-memory history unchanged.
        """
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a nonnegative integer.")
        with self._lock:
            spaces = self._get_spaces(style, max_length, category)
            if count == 0:
                return []
            available = [space.size - sum(space.contains(n) for n in self._used)
                         for space in spaces]
            remaining = sum(available)
            if count > remaining:
                raise NamePoolExhausted(
                    "Requested %d names, but only %d unused %s names fit %d "
                    "characters. Try 'mixed', a longer limit (up to 16), or "
                    "expand the dictionary." % (count, remaining, style, max_length))
            pending = set(self._used)
            result = []
            for _ in range(count):
                active = [i for i, amount in enumerate(available) if amount]
                chosen = self._rng.choice(active)
                name = self._choose_unused(spaces[chosen], pending)
                validate_name(name, max_length)
                pending.add(name.lower())
                result.append(name)
                available[chosen] -= 1
            self._save_history(pending)
            self._used = pending
            return result


# The simple helper remembers names for this Python session only. Use an
# explicit FantasyNameGenerator(history_path=...) for persistent app history.
_default_generator = FantasyNameGenerator()


def generate_name(style="mixed", max_length=MAX_NAME_LENGTH):
    """Quick session-unique helper; no files are created."""
    return _default_generator.generate(style=style, max_length=max_length)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=20, help="Names to print (default: 20).")
    parser.add_argument("--style", choices=STYLES, default="mixed")
    parser.add_argument("--max-length", type=int, default=16, help="2 through 16; includes spaces.")
    parser.add_argument("--seed", type=int, help="Reproducible preview sequence.")
    parser.add_argument("--history", help="Optional JSON history file, remembered across runs.")
    parser.add_argument("--json", action="store_true", help="Print the names as a JSON array.")
    parser.add_argument("--stats", action="store_true", help="Print pool counts instead of names.")
    args = parser.parse_args(argv)
    try:
        generator = FantasyNameGenerator(seed=args.seed, history_path=args.history)
        if args.stats:
            counts = {"first_names": len(FIRST_NAMES), "surnames": len(SURNAMES),
                      "max_length": args.max_length,
                      "unused_names": generator.remaining(args.style, args.max_length)}
            print(json.dumps(counts, indent=2))
        else:
            names = generator.generate_many(args.count, args.style, args.max_length)
            print(json.dumps(names, indent=2) if args.json else "\n".join(names))
    except (ValueError, NameHistoryError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
