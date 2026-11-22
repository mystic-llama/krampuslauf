# Fantasy Name Generator for Krampuslauf

Version 1.0.0 | Python 3.8+ | No additional packages

A general fantasy-name generator with readable syllables, optional first and
last names, strict length validation, and duplicate tracking. The Seeder applies
the character's appearance before reserving a fantasy name from the matching
race and sex library. If appearance customization is disabled, it uses the
default human male library. Naming controls live under **Automation > Appearance**.

Gargoyle libraries use single-word names. These are the available single-name
counts before accounting for used names.

| Race | Male | Female |
| --- | ---: | ---: |
| Human | 5,479 | 3,373 |
| Elf | 1,274 | 1,138 |
| Gargoyle | 5,496 | 3,381 |

Every pool screens invented names for common blocked fragments, including
fragments that span the space in a first-and-last name. The Seeder applies
this check to unsubmitted reservations before typing them. Ultima Online can
apply additional naming rules.

## What is included

- **8,917 first-name possibilities** in the generic pool: a curated bank plus combinations of
  complete, pronounceable syllables. Pronunciation is subjective; synthesized
  names are fantasy inventions, not a dictionary of verified real names.
- **468 curated surnames:** shorter names such as Vale, Wren, and Thorne,
  plus fantasy surnames such as Moonweave, Ashbrook, and Starfall.
- **2,881,883 distinct single or full names** that fit the default 16-character
  limit, before any names are reserved. This is a count of valid combinations,
  not a claim that millions of names were hand-written individually.
- One-word, first-and-last, or mixed output.
- ASCII letters only, with one optional space. No digits, punctuation, accents,
  trailing spaces, or name truncation. Spaces count toward the 16-character cap.
- Case-insensitive duplicate prevention across calls, batches, and styles.
- Optional JSON history to keep preventing duplicates after restarting the app.
- Custom dictionaries and optional random seeds for repeatable previews.

Example names include `Taren`, `Galaya Westfall`, `Faema Stormsong`,
`Calia Everbrook`, and `Thalarin Greyfen`.

## Quick integration

Copy `fantasy_name_generator.py` and `fantasy_name_libraries.py` beside Krampuslauf's main Python file.

```python
from fantasy_name_generator import FantasyNameGenerator

# Create this ONCE at application startup, then keep reusing it.
name_generator = FantasyNameGenerator(
    history_path="used_character_names.json"
)

# Whenever Krampuslauf needs a character name:
character_name = name_generator.generate(style="mixed", category="human_female")
```

Pass `character_name` to Krampuslauf's existing name-entry routine. The module
generates text; it does not change the interface, type into UO, or create a
character itself. The existing application has not been modified by this package.

Use an **absolute history path in Krampuslauf's existing user-data/settings
directory** when integrating into the packaged application. The relative path
above is convenient for a quick test but resolves against the working directory.

If a suitable Windows settings folder is not already available:

```python
import os
from pathlib import Path
from fantasy_name_generator import FantasyNameGenerator

data_directory = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Krampuslauf"
name_generator = FantasyNameGenerator(
    history_path=data_directory / "used_character_names.json"
)
```

The folder and history file are created when names are first generated or reserved.

## Output choices

```python
# One given name:
name_generator.generate(style="single")

# First and last name, including the space within the length limit:
name_generator.generate(style="full")

# Equal chance of either format while both still have unused names:
name_generator.generate(style="mixed", category="human_female")

# A batch with no internal duplicates and no repeats from prior calls:
batch = name_generator.generate_many(100, style="mixed")

# A smaller total length budget, if the host application needs one:
short_name = name_generator.generate(style="single", max_length=10)
```

`max_length` may be 2 through 16. A smaller budget can leave no usable names;
the generator reports that condition instead of shortening a name or adding digits.

## Duplicate handling

The same shared generator instance remembers every name it returns. A supplied
history path persists that set. Without a history path, tracking lasts only for
the lifetime of that instance.

```python
# Import existing character names to avoid reusing them:
name_generator.reserve(["Arin Vale", "Mira Wren"])

# These are treated as the same duplicate key:
name_generator.reserve(["ARIN VALE", "  Arin   Vale  "])

# Find how many names remain under a particular format and length:
remaining = name_generator.remaining(style="full", max_length=16)

# A copy of the lower-case duplicate keys, for your own settings system:
saved_names = sorted(name_generator.used_names)

# Or let Krampuslauf own persistence instead of using the module's JSON file:
other_generator = FantasyNameGenerator(used_names=saved_names)
```

Reservations are global within this generator/history, including across shards
if you reuse it for all shards. Use separate instances/history files only if you
intentionally want separate duplicate scopes. Generated attempts stay reserved
even when character creation is cancelled or rejected. Calling `generate()` again
therefore supplies a fresh candidate.

The history file is written atomically once per batch. Invalid history or a save
failure raises an error instead of silently forgetting used names. An impossible
batch reserves nothing. One instance may be shared between application threads;
give each history file one owning instance/process.

This checks local formatting and supplied/generated name history. It does not
query shard names or replace UO's own name-acceptance checks. The 16-character cap
is consistent with the [official UO name-length notice](https://uo.com/2023/11/30/publish-116-3-comes-to-tc1/).

## Validation and application errors

```python
from fantasy_name_generator import (
    is_valid_name, validate_name, NamePoolExhausted, NameHistoryError
)

assert is_valid_name("Arin Vale")
assert not is_valid_name("Arin123")
assert not is_valid_name("ThisNameIsTooLongHere")

# Returns the unchanged name on success; raises ValueError on invalid input.
validate_name("Arin Vale")

try:
    character_name = name_generator.generate(style="mixed", category="human_female")
except (NamePoolExhausted, NameHistoryError, ValueError) as error:
    # Connect this to Krampuslauf's existing status/error display.
    print(str(error))
```

## Dictionary customization

The clearly marked section near the top of the module contains
`CURATED_FIRST_NAMES`, `FIRST_SYLLABLES`, `LAST_SYLLABLES`, and `SURNAMES`.
Add space-separated entries inside the triple-quoted strings.

First syllables end in vowels; ending syllables begin with consonants. This keeps
joins readable. If you prefer only the curated first names or want your own list:

```python
from fantasy_name_generator import FantasyNameGenerator, CURATED_FIRST_NAMES

curated_only = FantasyNameGenerator(first_names=CURATED_FIRST_NAMES)
custom = FantasyNameGenerator(
    first_names=("Arin", "Mira", "Thalen"),
    surnames=("Vale", "Moonweave", "Starfall"),
)
```

Dictionary entries must be individual words. First and last names identical
ignoring case, such as `Rowan Rowan`, are not generated. Customizing the banks
changes the available-name counts.

## Run it directly

```text
python fantasy_name_generator.py
python fantasy_name_generator.py --count 30 --style full
python fantasy_name_generator.py --count 30 --style mixed --seed 42
python fantasy_name_generator.py --count 100 --history used_character_names.json
python fantasy_name_generator.py --count 20 --json
python fantasy_name_generator.py --stats
```

For the simplest session-only use in another script:

```python
from fantasy_name_generator import generate_name
name = generate_name()
```

## Verification

Run the included standard-library tests from the project root:

```text
python -m unittest discover -s tests -p test_fantasy_name_generator.py -v
```

The tests cover a 25,000-name unique batch; format and length boundaries; saved
history across restarts; case-insensitive reservations; exact small-pool
exhaustion; failure to save history; and concurrent calls to one instance.
The package is intended for the desktop application's CPython runtime, not a
Razor Enhanced IronPython script. No live UO client testing has been performed.
