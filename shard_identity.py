"""Read the optional `(Shard Name)` suffix from a Classic Client window title.

No account names are returned or recorded. This only validates the caption after
selecting a shard; it does not read the custom-drawn shard-list text.
"""
import re


def shard_from_title(title, known_shards):
    """Return canonical shard name or None if no recognized final suffix exists."""
    if not isinstance(title, str):
        return None
    match = re.search(r"\(([^()]*)\)\s*$", title)
    if not match:
        return None
    value = " ".join(match.group(1).strip().split()).casefold()
    matches = [s for s in known_shards if " ".join(s.strip().split()).casefold() == value]
    return matches[0] if len(matches) == 1 else None
