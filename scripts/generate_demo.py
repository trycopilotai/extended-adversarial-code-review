#!/usr/bin/env python3
"""Generate the terminal demo and its static poster.

Both images are reconstructed from the recorded session in
evidence/transcripts/round-yield-explain.txt. Every line they
show is copied from that file, so the demo cannot say
something the program did not print.

    python3 scripts/generate_demo.py            # write both
    python3 scripts/generate_demo.py --check    # compare only

The demo reveals the session in steps and loops. Each step
stays on screen until the loop restarts, so a later frame
always contains every earlier one. The poster is the last
frame with no animation, for a reader who asked for reduced
motion.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "round-yield-explain.txt"
DEMO = ROOT / "assets" / "demo.svg"
POSTER = ROOT / "assets" / "poster.svg"
SOURCE_LABEL = (
    "Reconstructed from evidence/transcripts/round-yield-explain.txt"
)

WIDTH = 1280
HEIGHT = 680
MARGIN_X = 40
FIRST_BASELINE = 112
LINE_HEIGHT = 28
STEP_GAP = 14
FONT_SIZE = 18
# A monospace glyph is about 0.6 em wide. The verifier uses
# the same figure to prove the longest line fits the canvas.
GLYPH_WIDTH = 0.6 * FONT_SIZE
LABEL_FONT_SIZE = 16

BACKGROUND = "#101418"
TEXT = "#f7fbff"
MUTED = "#a7bac5"
WARN = "#ffd166"
GOOD = "#55d6be"
CHROME = ("#ff6b6b", "#ffd166", "#55d6be")

LOOP_SECONDS = 12
# Percent of the loop at which each step appears. Every step
# holds until HOLD_UNTIL, then the loop restarts.
REVEAL_AT = (8, 36, 66)
FADE_IN = 4
HOLD_UNTIL = 94

COMMAND_PREFIX = "$ python3 "
CLAUSE_COUNT = 7


def session_lines(transcript: str) -> list[str]:
    return transcript.splitlines()


def block_after(lines: list[str], heading: str) -> list[str]:
    """The heading line and the lines under it, up to a blank."""
    if heading not in lines:
        raise ValueError("the transcript has no %r block" % heading)
    start = lines.index(heading)
    block = [heading]
    for line in lines[start + 1 :]:
        if line.strip() == "":
            break
        block.append(line)
    return block


def steps_from_transcript(transcript: str) -> tuple[str, list[list[str]]]:
    """The command, then the three blocks the demo reveals."""
    lines = session_lines(transcript)
    if not lines or not lines[0].startswith(COMMAND_PREFIX):
        raise ValueError("the transcript does not start with the command")
    command = lines[0]
    curve = block_after(lines, "yield curve")
    clauses = block_after(lines, "clauses")
    if len(clauses) != CLAUSE_COUNT + 1:
        raise ValueError(
            "expected %d clause lines, found %d"
            % (CLAUSE_COUNT, len(clauses) - 1)
        )
    if "STOP" in lines:
        verdict = "STOP"
    elif "CONTINUE" in lines:
        verdict = "CONTINUE"
    else:
        raise ValueError("the transcript carries no verdict")
    tail = lines[-2:]
    if not tail[0].startswith("$ echo") or not tail[1].startswith(
        "exit status: "
    ):
        raise ValueError("the transcript does not end with the exit status")
    return command, [curve, clauses, [verdict] + tail]


def line_colour(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("$ "):
        return TEXT
    if stripped.startswith("FIRED") or stripped == "STOP":
        return WARN
    if stripped.startswith("quiet") or stripped == "CONTINUE":
        return GOOD
    if stripped in ("yield curve", "clauses"):
        return MUTED
    return TEXT


def text_element(line: str, baseline: int) -> str:
    return (
        '    <text x="%d" y="%d" fill="%s" xml:space="preserve">%s</text>'
        % (MARGIN_X, baseline, line_colour(line), html.escape(line))
    )


def layout(command: str, steps: list[list[str]]) -> tuple[list[str], int]:
    """SVG fragments for the command and each step, and the last baseline."""
    fragments = [text_element(command, FIRST_BASELINE)]
    baseline = FIRST_BASELINE
    for index, block in enumerate(steps):
        baseline += STEP_GAP
        fragments.append('    <g class="step-%d">' % (index + 1))
        for line in block:
            baseline += LINE_HEIGHT
            fragments.append("  " + text_element(line, baseline))
        fragments.append("    </g>")
    return fragments, baseline


def animation_css() -> str:
    rules = []
    for index, reveal in enumerate(REVEAL_AT):
        number = index + 1
        rules.append(
            "    .step-%d {\n"
            "      opacity: 0;\n"
            "      animation: reveal-%d %ds infinite;\n"
            "    }" % (number, number, LOOP_SECONDS)
        )
        rules.append(
            "    @keyframes reveal-%d {\n"
            "      0%%, %d%% { opacity: 0; }\n"
            "      %d%%, %d%% { opacity: 1; }\n"
            "      100%% { opacity: 0; }\n"
            "    }" % (number, reveal, reveal + FADE_IN, HOLD_UNTIL)
        )
    selectors = ", ".join(".step-%d" % (i + 1) for i in range(len(REVEAL_AT)))
    rules.append(
        "    @media (prefers-reduced-motion: reduce) {\n"
        "      %s {\n"
        "        opacity: 1;\n"
        "        animation: none;\n"
        "      }\n"
        "    }" % selectors
    )
    return "\n".join(rules)


def render(transcript: str, animated: bool) -> str:
    command, steps = steps_from_transcript(transcript)
    fragments, last_baseline = layout(command, steps)
    label_baseline = HEIGHT - 28
    if last_baseline + LINE_HEIGHT > label_baseline - LABEL_FONT_SIZE:
        raise ValueError("the session does not fit the canvas")
    if animated:
        title = "Animated round_yield.py session"
        style = "  <style>\n%s\n  </style>\n" % animation_css()
    else:
        title = "round_yield.py session"
        style = ""
    description = (
        "A terminal runs round_yield.py with --explain on a synthetic "
        "record. It prints the yield curve, the state of each of seven "
        "stopping clauses, and the verdict with its exit status."
    )
    chrome = "\n".join(
        '  <circle cx="%d" cy="44" r="9" fill="%s" />' % (40 + 30 * i, colour)
        for i, colour in enumerate(CHROME)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-labelledby="title description">\n'
        '  <title id="title">%s</title>\n'
        '  <desc id="description">%s</desc>\n'
        "%s"
        '  <rect width="%d" height="%d" rx="24" fill="%s" />\n'
        "%s\n"
        '  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">\n'
        "%s\n"
        "  </g>\n"
        '  <text x="%d" y="%d" fill="%s" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">%s</text>\n'
        "</svg>\n"
        % (
            WIDTH,
            HEIGHT,
            WIDTH,
            HEIGHT,
            title,
            description,
            style,
            WIDTH,
            HEIGHT,
            BACKGROUND,
            chrome,
            FONT_SIZE,
            "\n".join(fragments),
            MARGIN_X,
            label_baseline,
            MUTED,
            LABEL_FONT_SIZE,
            SOURCE_LABEL,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if either committed image differs from a fresh render",
    )
    arguments = parser.parse_args(argv)
    transcript = TRANSCRIPT.read_text(encoding="utf-8")
    outputs = (
        (DEMO, render(transcript, animated=True)),
        (POSTER, render(transcript, animated=False)),
    )
    if arguments.check:
        stale = [
            path.name
            for path, text in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            print("stale: %s. Run scripts/generate_demo.py." % ", ".join(stale))
            return 1
        print("demo.svg and poster.svg match the transcript")
        return 0
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
