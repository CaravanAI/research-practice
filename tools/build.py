#!/usr/bin/env python3
"""Build the research board and the plugin marketplace list.

Usage:
    python tools/build.py           check everything, then rebuild
                                    docs/index.html and .claude-plugin/marketplace.json
    python tools/build.py --check   only check cards and plugins (no files written)

Python 3, standard library only.

Why this exists: every person adds their OWN card file and their OWN plugin
folder. Nobody edits a shared file, so 13 people can open pull requests at the
same time without merge conflicts. This script is the one place that stitches
those separate files into the board page and the marketplace list.
"""

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "cards"
PLUGINS_DIR = ROOT / "plugins"
BOARD_FILE = ROOT / "docs" / "index.html"
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"

STAGES = ["Idea", "Researching", "Group presentation", "Decision"]
MARKETPLACE_NAME = "seafarer-practice"
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def is_text(value):
    return isinstance(value, str) and value.strip() != ""


def check_card(path, data):
    """Return a list of plain-English problems with one card."""
    problems = []
    where = f"{path.name}"

    if not isinstance(data, dict):
        return [f"{where}: the file must hold one card (a JSON object)."]

    for field in ("name", "country", "sector", "owner"):
        if not is_text(data.get(field)):
            problems.append(f'{where}: "{field}" is missing or empty.')

    stage = data.get("stage")
    if stage not in STAGES:
        problems.append(
            f'{where}: "stage" is {stage!r}. It must be exactly one of: '
            + ", ".join(STAGES) + "."
        )

    key_number = data.get("key_number")
    if not isinstance(key_number, dict) or not is_text(key_number.get("label")) \
            or not is_text(key_number.get("value")):
        problems.append(f'{where}: "key_number" needs a "label" and a "value".')

    source = data.get("source")
    page = source.get("page") if isinstance(source, dict) else None
    page_ok = is_text(page) or (isinstance(page, int) and not isinstance(page, bool))
    if not isinstance(source, dict) or not is_text(source.get("document")) or not page_ok:
        problems.append(f'{where}: "source" needs a "document" and a "page".')

    if "flag" in data:
        flag = data["flag"]
        flag_page = flag.get("page") if isinstance(flag, dict) else None
        flag_page_ok = is_text(flag_page) or (
            isinstance(flag_page, int) and not isinstance(flag_page, bool))
        if (not isinstance(flag, dict) or flag.get("status") != "Wrong"
                or not is_text(flag.get("corrected_value")) or not flag_page_ok):
            problems.append(
                f'{where}: "flag" must have "status": "Wrong", a "corrected_value" '
                'and a "page". Remove "flag" if the card is not flagged.'
            )

    return problems


def load_cards():
    """Read every card file. Returns (cards, problems)."""
    cards, problems = [], []
    for path in sorted(CARDS_DIR.glob("*.json")):
        if not SLUG_RE.match(path.stem):
            problems.append(
                f"{path.name}: the file name should be lowercase words joined by "
                "hyphens, like bintulu-port-holdings.json."
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            problems.append(f"{path.name}: this is not valid JSON ({err}).")
            continue
        card_problems = check_card(path, data)
        problems.extend(card_problems)
        if not card_problems:
            cards.append(data)
    return cards, problems


def load_plugins():
    """Read every plugin folder. Returns (plugins, problems)."""
    plugins, problems = [], []
    if not PLUGINS_DIR.is_dir():
        return plugins, problems
    for folder in sorted(p for p in PLUGINS_DIR.iterdir() if p.is_dir()):
        label = f"plugins/{folder.name}"
        manifest = folder / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            problems.append(f"{label}: missing .claude-plugin/plugin.json.")
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            problems.append(f"{label}/.claude-plugin/plugin.json: not valid JSON ({err}).")
            continue
        if not isinstance(data, dict):
            problems.append(f"{label}/.claude-plugin/plugin.json: must be a JSON object.")
            continue

        found = []
        if not is_text(data.get("name")):
            found.append(f'{label}: plugin.json needs a "name".')
        elif not SLUG_RE.match(data["name"]):
            found.append(f'{label}: "name" must be lowercase words joined by hyphens.')
        elif data["name"] != folder.name:
            found.append(
                f'{label}: "name" is "{data["name"]}" but the folder is '
                f'"{folder.name}". They must match.'
            )
        if not is_text(data.get("version")):
            found.append(f'{label}: plugin.json needs a "version", like "1.0.0".')
        if not is_text(data.get("description")):
            found.append(f'{label}: plugin.json needs a "description".')
        has_agent = any((folder / "agents").glob("*.md"))
        has_skill = any((folder / "skills").glob("*/SKILL.md"))
        if not (has_agent or has_skill):
            found.append(
                f"{label}: add at least one agent (agents/<name>.md) or one skill "
                "(skills/<name>/SKILL.md)."
            )
        problems.extend(found)
        if not found:
            plugins.append(data)
    return plugins, problems


# ---------------------------------------------------------------------------
# Marketplace
# ---------------------------------------------------------------------------

def build_marketplace(plugins):
    return {
        "name": MARKETPLACE_NAME,
        "description": "Practice agents and skills from the Seafarer training",
        "owner": {"name": "Caravan"},
        "plugins": [
            {
                "name": p["name"],
                "source": f"./plugins/{p['name']}",
                "description": p["description"],
            }
            for p in sorted(plugins, key=lambda p: p["name"])
        ],
    }


# ---------------------------------------------------------------------------
# Board page
# ---------------------------------------------------------------------------

def last_updated():
    """Time of the last commit that touched cards or plugins.

    Using the commit time (not "now") means rebuilding without any change gives
    the identical page, so the automation does not make endless empty commits.
    Falls back to the current time if git history is not available.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", "cards", "plugins"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        when = datetime.fromisoformat(out)
    except Exception:
        when = datetime.now(timezone.utc)
    return when.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def esc(value):
    return html.escape(str(value), quote=True)


def render_card(card):
    flag = card.get("flag")
    flagged = isinstance(flag, dict)
    banner = ""
    if flagged:
        banner = (
            '<div class="flag"><strong>Flagged</strong>'
            f'<span>Corrected value: {esc(flag["corrected_value"])} '
            f'(page {esc(flag["page"])})</span></div>'
        )
    kn = card["key_number"]
    src = card["source"]
    return (
        f'<article class="card{" is-flagged" if flagged else ""}">'
        f"{banner}"
        f'<h3>{esc(card["name"])}</h3>'
        f'<p class="meta">{esc(card["country"])} &middot; {esc(card["sector"])}</p>'
        f'<div class="number"><span class="label">{esc(kn["label"])}</span>'
        f'<span class="value{" struck" if flagged else ""}">{esc(kn["value"])}</span></div>'
        f'<p class="source">Source: {esc(src["document"])}, page {esc(src["page"])}</p>'
        f'<p class="owner">{esc(card["owner"])}</p>'
        "</article>"
    )


def render_board(cards):
    columns = []
    for stage in STAGES:
        in_stage = sorted((c for c in cards if c["stage"] == stage),
                          key=lambda c: c["name"].lower())
        body = "".join(render_card(c) for c in in_stage) or '<p class="empty">No cards yet</p>'
        columns.append(
            f'<section class="column"><h2>{esc(stage)}'
            f'<span class="count">{len(in_stage)}</span></h2>{body}</section>'
        )

    return PAGE.format(
        count=len(cards),
        noun="card" if len(cards) == 1 else "cards",
        updated=esc(last_updated()),
        columns="".join(columns),
    )


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seafarer research board (practice)</title>
<style>
  :root {{
    --paper: #F0EEE0;
    --clay: #802A02;
    --forest: #2B3901;
    --ink: #131313;
    --card: #FBFAF3;
    --line: #D9D5BF;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: "Instrument Sans", "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
    font-size: 20px;
    line-height: 1.3;
  }}
  header {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px 32px;
    padding: 20px 32px;
    border-bottom: 6px solid var(--clay);
  }}
  h1 {{ margin: 0; font-size: 40px; color: var(--clay); font-weight: 700; }}
  .stats {{ font-size: 24px; color: var(--forest); font-weight: 600; }}
  .stats span + span {{ margin-left: 28px; }}
  main {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 20px;
    padding: 20px 32px 32px;
    align-items: start;
  }}
  .column h2 {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0 0 14px;
    padding: 10px 16px;
    background: var(--forest);
    color: var(--paper);
    font-size: 26px;
    border-radius: 8px;
  }}
  .count {{
    background: var(--paper);
    color: var(--forest);
    border-radius: 999px;
    min-width: 40px;
    text-align: center;
    padding: 0 12px;
    font-size: 24px;
  }}
  .card {{
    background: var(--card);
    border: 2px solid var(--line);
    border-left: 8px solid var(--clay);
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 16px;
  }}
  .card.is-flagged {{ border-color: var(--clay); border-left-width: 8px; }}
  .card h3 {{ margin: 0 0 4px; font-size: 26px; line-height: 1.15; }}
  .meta {{ margin: 0 0 12px; font-size: 20px; color: var(--forest); font-weight: 600; }}
  .number {{
    background: var(--paper);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 10px;
  }}
  .number .label {{ display: block; font-size: 17px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .number .value {{ display: block; font-size: 32px; font-weight: 700; color: var(--clay); line-height: 1.15; }}
  .value.struck {{ text-decoration: line-through; text-decoration-thickness: 3px; }}
  .source {{ margin: 0 0 8px; font-size: 17px; }}
  .owner {{ margin: 0; font-size: 18px; font-weight: 700; color: var(--forest); }}
  .owner::before {{ content: "Owner: "; font-weight: 500; color: var(--ink); }}
  .flag {{
    background: var(--clay);
    color: #fff;
    margin: -16px -18px 12px;
    padding: 10px 18px;
    border-radius: 4px 4px 0 0;
    font-size: 20px;
  }}
  .flag strong {{ display: block; font-size: 26px; text-transform: uppercase; letter-spacing: 0.06em; }}
  .empty {{ color: #6b6a5c; font-size: 20px; padding: 8px 4px; }}
  @media (max-width: 1100px) {{
    main {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  }}
  @media (max-width: 640px) {{
    main {{ grid-template-columns: 1fr; padding: 16px; }}
    header {{ padding: 16px; }}
    h1 {{ font-size: 30px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Seafarer research board &middot; practice</h1>
  <div class="stats"><span>{count} {noun}</span><span>Last updated {updated}</span></div>
</header>
<main>
{columns}
</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    check_only = "--check" in sys.argv[1:]

    cards, card_problems = load_cards()
    plugins, plugin_problems = load_plugins()
    problems = card_problems + plugin_problems

    if problems:
        print("Problems found. Please fix these and try again:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    if check_only:
        print(f"All good: {len(cards)} cards and {len(plugins)} plugins checked.")
        return 0

    write_if_changed(BOARD_FILE, render_board(cards))
    marketplace = json.dumps(build_marketplace(plugins), indent=2) + "\n"
    write_if_changed(MARKETPLACE_FILE, marketplace)
    print(f"Built the board ({len(cards)} cards) and the marketplace ({len(plugins)} plugins).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
