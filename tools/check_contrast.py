#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assert every text colour the themes emit clears WCAG 2.1 AA.

Why this COMPILES the Sass instead of reading it: the bug class it was written for
is a value that looks right in the source and ships as something else. `mix(...)`
written outside `#{}` emits the literal text `mix(#000, #2f7f93, 25%)` into the CSS.
That is not a CSS function, so the custom property is invalid at computed-value
time and the browser silently falls back to an inherited colour. Three variables in
this repo shipped that way for as long as the theme has been here. Reading the
.scss cannot distinguish that from a working value; reading the compiled output can.

Why it checks the footer separately: `--global-text-color-light` is used both on the
white body and on the `#f2f3f3` footer, and `.page__footer a` forces `color:inherit`.
A value chosen against white alone can pass here and still fail down there, so both
backgrounds are asserted. That is not hypothetical -- `#6f757c` passes on white at
4.65:1 and fails the footer at 4.19:1.

Run:  python tools/check_contrast.py              # 0 = every colour clears AA
      python tools/check_contrast.py --self-test  # prove the guards can go red

Needs libsass (`pip install libsass`). Ruby/Jekyll are not required.
"""
import io
import os
import re
import sys

try:
    import sass
except ImportError:
    print("needs libsass:  pip install libsass")
    sys.exit(2)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIGHT = os.path.join(REPO, "_sass", "theme", "_default_light.scss")
DARK = os.path.join(REPO, "_sass", "theme", "_default_dark.scss")


# ---------- WCAG 2.1 relative luminance and contrast ----------

def _expand(h):
    h = h.lstrip("#")
    return "".join(c * 2 for c in h) if len(h) == 3 else h


def _linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    h = _expand(hex_colour)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _check_the_checker():
    """Four pairs whose ratios the spec fixes exactly.

    Without this the formula could be quietly wrong in a direction that makes
    everything pass, and the report would look identical to a real all-clear.
    """
    for fg, bg, want in (("#000000", "#ffffff", 21.0),
                         ("#ffffff", "#ffffff", 1.0),
                         ("#767676", "#ffffff", 4.54),
                         ("#2f7f93", "#ffffff", 4.59)):
        got = contrast(fg, bg)
        if abs(got - want) > 0.02:
            print("contrast formula is wrong: %s on %s gave %.2f, spec says %.2f"
                  % (fg, bg, got, want))
            return False
    return True


# ---------- what must hold ----------

WHITE = "#ffffff"
FOOTER = "#f2f3f3"
DARK_BG = "#474747"

LIGHT_RULES = [
    ("--global-link-color", [WHITE], "every <a>"),
    ("--global-link-color-hover", [WHITE], "link hover"),
    ("--global-link-color-visited", [WHITE], "link visited"),
    ("--global-text-color", [WHITE], "body text"),
    ("--global-text-color-light", [WHITE, FOOTER], "muted text and the footer"),
    ("--global-fig-caption-color", [WHITE], "figure captions"),
    ("--global-masthead-link-color", [WHITE], "masthead"),
    ("--global-masthead-link-color-hover", [WHITE], "masthead hover"),
]

DARK_RULES = [
    ("--global-link-color", [DARK_BG], "every <a>"),
    ("--global-link-color-hover", [DARK_BG], "link hover"),
    ("--global-link-color-visited", [DARK_BG], "link visited"),
    ("--global-text-color", [DARK_BG], "body text"),
    ("--global-text-color-light", [DARK_BG], "muted text"),
    ("--global-fig-caption-color", [DARK_BG], "figure captions"),
]

# Normal-size text. The large-text 3:1 allowance is deliberately NOT used: these
# are variables, not elements, and the same variable paints both sizes.
NEED = 4.5

HEX = re.compile(r"^#[0-9a-fA-F]{3,8}$")
VAR = re.compile(r"(--global-[\w-]+)\s*:\s*([^;]+);")


def emitted_colours(scss_path):
    """Compile one theme file and return the custom properties it actually ships."""
    src = open(scss_path, encoding="utf-8").read()
    css = sass.compile(string=src, include_paths=[os.path.join(REPO, "_sass")])
    return {name: value.strip() for name, value in VAR.findall(css)}


def run(quiet=False):
    bad = 0
    for label, path, rules in (("light  _default_light.scss", LIGHT, LIGHT_RULES),
                               ("dark   _default_dark.scss", DARK, DARK_RULES)):
        if not quiet:
            print("=" * 72)
            print(label)
            print("=" * 72)
        values = emitted_colours(path)
        for var, backgrounds, what in rules:
            value = values.get(var)
            if value is None:
                if not quiet:
                    print("  ??  %-36s not defined" % var)
                continue
            if not HEX.match(value):
                bad += 1
                if not quiet:
                    print("  !!  %-36s = %s" % (var, value))
                    print("      not a CSS colour, so this property is invalid and "
                          "falls back silently")
                continue
            for bg in backgrounds:
                ratio = contrast(value, bg)
                if ratio < NEED:
                    bad += 1
                if not quiet:
                    print("  %s  %-36s = %-9s on %s = %5.2f:1  (needs %.1f)  %s"
                          % ("!!" if ratio < NEED else "ok", var, value, bg,
                             ratio, NEED, what))
    if not quiet:
        print()
        print("%d problem(s)" % bad if bad else
              "every colour clears AA and compiles to a real hex value")
    return 1 if bad else 0


def self_test():
    """Break each guard in turn and require it to go red.

    A checker that cannot fail prints the same green as one that found nothing.
    These three mutations are the three real failure shapes seen in this repo: a
    colour that is simply too faint, a colour that passes on one background and
    fails on another it also sits on, and a value that reads correctly in the
    source but ships as a literal `mix(...)` string.
    """
    good = open(LIGHT, encoding="utf-8").read()
    mutations = [
        ("a link colour too faint to read",
         "--global-link-color                 : #2c7a8c;",
         "--global-link-color                 : #52adc8;"),
        ("passes on white, fails on the footer it also paints",
         "--global-text-color-light           : #666b70;",
         "--global-text-color-light           : #6f757c;"),
        ("mix() outside #{} ships as a literal string",
         "--global-link-color-hover           : #{mix(#000, $primary-color, 25%)};",
         "--global-link-color-hover           : mix(#000, $primary-color, 25%);"),
    ]
    every_one_caught = True
    for name, original, broken in mutations:
        if original not in good:
            print("SELF-TEST INCONCLUSIVE: the anchor for %r is gone, so this "
                  "mutation proved nothing" % name)
            return 2
        open(LIGHT, "w", encoding="utf-8").write(good.replace(original, broken, 1))
        try:
            caught = run(quiet=True) != 0
        finally:
            open(LIGHT, "w", encoding="utf-8").write(good)
        print("  %s  %s" % ("caught " if caught else "MISSED ", name))
        every_one_caught &= caught
    if not every_one_caught:
        print("SELF-TEST FAILED: a mutation slipped past the check")
        return 2
    print("self-test ok: every guard goes red when broken")
    return 0


def main():
    if not _check_the_checker():
        return 2
    if "--self-test" in sys.argv:
        return self_test()
    return run()


if __name__ == "__main__":
    sys.exit(main())
