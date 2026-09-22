#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render `_includes/archive-single.html` and assert it emits nothing for an
entry with no title.

Why this exists. `site.pages` is not "the pages the author wrote". It holds every
file Jekyll processes that carries front matter, which on this site includes build
artefacts (`assets/css/main.css`, `images/manifest.json`, `feed.xml`, `robots.txt`)
and every stub `jekyll-redirect-from` generates (`/about/`, `/resume`, `/nmp.html`,
and so on). None of those have a title, so the include used to render
`<h2 class="archive__item-title"><a href="..." rel="permalink"></a></h2>` for each:
an anchor with no accessible name inside a heading with no accessible text. One DOM
node, two WCAG failures. An accessibility scan on 2026-09-22 reported link-name and
empty-heading with identical counts on exactly the three pages that loop over
`site.pages`, which is the signature of a single shared defect rather than nine
separate authoring mistakes.

Run:  python tools/test_archive_guard.py      (needs `pip install python-liquid`)

The last block is a negative control. Without it a green run would also be what you
get from a test that can no longer fail.
"""
import io
import os
import re
import sys

try:
    from liquid import Environment
except ImportError:
    print("needs python-liquid:  pip install python-liquid")
    sys.exit(2)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO, "_includes", "archive-single.html")

EMPTY_ANCHOR = re.compile(r"<a\b[^>]*>\s*</a>")
_HEADING = re.compile(r"<(h[1-6])\b[^>]*>(.*?)</\1>", re.S)


def has_empty_heading(html):
    """axe's empty-heading fires on ACCESSIBLE TEXT, not on a literally empty tag.

    The defect renders `<h2><a href=...></a></h2>`. The heading HAS a child, so a
    naive `<h2>\\s*</h2>` pattern never matches it and the test would pass while the
    real page fails. Strip the markup inside the heading and judge the text.
    """
    for _tag, inner in _HEADING.findall(html):
        if re.sub(r"<[^>]+>", "", inner).strip() == "":
            return True
    return False


def load_template(source):
    """Strip the Jekyll-only `{% include %}` tags so plain Liquid can parse this."""
    return re.sub(r"\{%\s*include [^%]*%\}", "", source)


def render(template, post):
    return template.render(post=post, base_path="",
                           site={"teaser": None, "read_more": ""},
                           include={"type": "list"})


# Taken verbatim from the live /sitemap/ output on 2026-09-22.
UNTITLED = [
    {"url": "/assets/css/main.css"},
    {"url": "/images/manifest.json"},
    {"url": "/feed.xml"},
    {"url": "/robots.txt"},
    {"url": "/about/"},
    {"url": "/resume"},
    {"url": "/nmp.html"},
    {"title": "", "url": "/empty-string/"},
    {"title": "   ", "url": "/whitespace-only/"},
]

TITLED = [
    {"title": "Publications", "url": "/publications/"},
    {"title": "01:198:461 Machine Learning Principles (TA)",
     "url": "/teaching/2025-fall-cs461/", "collection": "teaching",
     "type": "Recitation", "venue": "Rutgers University", "date": "2025-09-01"},
    {"title": "Sitemap", "url": "/sitemap/"},
]


def main():
    source = load_template(open(TEMPLATE, encoding="utf-8").read())
    env = Environment()
    template = env.from_string(source)
    failures = 0

    print("untitled entries must render nothing")
    for post in UNTITLED:
        out = render(template, post)
        ok = out.strip() == ""
        failures += 0 if ok else 1
        print("  %s %-28s %s" % ("ok " if ok else "!! ", post.get("url"),
                                 "" if ok else repr(out.strip()[:80])))

    print()
    print("titled entries must still render a link with a name")
    for post in TITLED:
        out = render(template, post)
        ok = (out.strip() != "" and post["title"] in out
              and not EMPTY_ANCHOR.search(out) and not has_empty_heading(out))
        failures += 0 if ok else 1
        print("  %s %s" % ("ok " if ok else "!! ", post["title"][:52]))

    print()
    print("negative control: with the guard removed, both failures must come back")
    without_guard = source.replace('{% if archive_title != "" %}', "{% if true %}")
    if without_guard == source:
        print("  !!  the guard is not in the template at all")
        failures += 1
    else:
        out = render(env.from_string(without_guard), {"url": "/assets/css/main.css"})
        anchor = EMPTY_ANCHOR.search(out) is not None
        heading = has_empty_heading(out)
        if anchor and heading:
            print("  ok  reproduced an unnamed anchor and an empty heading")
        else:
            print("  !!  did not reproduce (anchor=%s heading=%s), so a green run "
                  "above would prove nothing" % (anchor, heading))
            failures += 1

    print()
    print("FAILED: %d" % failures if failures else
          "all good: untitled entries drop out, titled ones survive, "
          "and the check can fail")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
