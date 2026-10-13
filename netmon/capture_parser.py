"""
Splits a raw pasted CLI capture (the kind you get from copy-pasting a
terminal session across several devices into one .txt file) into
individual (host, command, output) blocks — so the same parsers.py
functions used for live SSH can run on manually-captured text too.

Works off Cisco-style prompts: a line that looks like
    HOSTNAME#some command
starts a block; the block's content runs until the next such line
(including a bare "HOSTNAME#" with no command, which just closes the
previous block and is discarded).
"""
import re

_PROMPT_RE = re.compile(r"^(?P<host>[\w\-\.]+)#(?P<cmd>.*)$", re.MULTILINE)
_SECTION_HINT_RE = re.compile(r"^-{2,}\s*(?P<hint>.+?)\s*-{2,}$")


def split_capture(text: str) -> list:
    """Returns a list of dicts: {host, command, raw, section_hint}.
    section_hint is the nearest preceding '---Some Label---' divider
    line, if any (your sample log uses these, e.g. '---To-Internet-CBN---') —
    handy as a suggestion when filling in config/capture_map.yaml."""
    matches = list(_PROMPT_RE.finditer(text))
    blocks = []
    current_hint = None

    for i, m in enumerate(matches):
        # Track the most recent section divider seen before this prompt.
        preceding_text = text[matches[i - 1].end() if i > 0 else 0:m.start()]
        for line in preceding_text.splitlines():
            hint_m = _SECTION_HINT_RE.match(line.strip())
            if hint_m:
                current_hint = hint_m.group("hint")

        host = m.group("host")
        cmd = m.group("cmd").strip()
        if not cmd:
            continue  # bare "hostname#" prompt — just a block terminator

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[start:end].strip("\n")

        blocks.append({"host": host, "command": cmd, "raw": raw, "section_hint": current_hint})

    return blocks
