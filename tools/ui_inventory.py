"""
Print Tempo's UI inventory, one entry per line.

The UI guard snapshots this output before a surface edit and compares it afterwards, so a
dropped control, action, handler or theme token shows up as a lost line. The dump is pure
parsing: it never starts a server or a browser, and its order is sorted and stable.

Usage: python tools/ui_inventory.py [web-directory]

PRINCIPLE-003, PRINCIPLE-010, PRINCIPLE-015.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Set

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
HANDLER_PATTERN = re.compile(r"^\s*var ACTIONS = \{(?P<body>[^}]*)\}", re.MULTILINE)
KEY_PATTERN = re.compile(r"(\w+)\s*:")
TOKEN_PATTERN = re.compile(r"^\s*(--[a-z0-9-]+)\s*:", re.MULTILINE)
ARIA_PATTERN = re.compile(r"aria-label(?:ledby)?")


class SurfaceParser(HTMLParser):
    """Collects the identified elements, named actions and live regions of one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: Set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {name: value or "" for name, value in attrs}
        element = values.get("id")
        if element:
            self.entries.add(f"element {tag}#{element}")
        action = values.get("data-action")
        if action:
            self.entries.add(f"action {action}")
        if "aria-live" in values:
            self.entries.add(f"live-region {values.get('id') or tag}")
        if values.get("role"):
            self.entries.add(f"role {values['role']}")


def html_entries(path: Path) -> Set[str]:
    """Identified elements, actions, roles and live regions declared in a page."""
    parser = SurfaceParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser.entries


def handler_entries(path: Path) -> Set[str]:
    """Action names the browser script is willing to dispatch."""
    match = HANDLER_PATTERN.search(path.read_text(encoding="utf-8"))
    if not match:
        return set()
    return {f"handler {name}" for name in KEY_PATTERN.findall(match.group("body"))}


def token_entries(path: Path) -> Set[str]:
    """Theme custom properties the stylesheet declares."""
    text = path.read_text(encoding="utf-8")
    return {f"token {name}" for name in TOKEN_PATTERN.findall(text)}


def inventory(web: Path) -> List[str]:
    """Every inventory entry of a web directory, sorted and deduplicated."""
    entries: Set[str] = set()
    for page in sorted(web.glob("*.html")):
        entries |= html_entries(page)
    for script in sorted(web.glob("*.js")):
        entries |= handler_entries(script)
    theme = web / "theme.css"
    if theme.exists():
        entries |= token_entries(theme)
    return sorted(entries)


def main(argv: List[str]) -> int:
    """Write the inventory to stdout; exit 1 when the surface has no entries at all."""
    web = Path(argv[1]).resolve() if len(argv) > 1 else WEB_DIR
    if not web.is_dir():
        print(f"no such web directory: {web}", file=sys.stderr)
        print("Why: the inventory proof needs Tempo's web/ surface.", file=sys.stderr)
        print("Fix: run it from the project root, or pass the directory.", file=sys.stderr)
        return 2
    entries = inventory(web)
    if not entries:
        print(f"no UI inventory found under {web}", file=sys.stderr)
        print("Why: an empty inventory would hide every lost control.", file=sys.stderr)
        print("Fix: check that web/index.html still carries ids and data-action buttons.",
              file=sys.stderr)
        return 1
    print("\n".join(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
