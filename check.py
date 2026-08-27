#!/usr/bin/env python3
"""Validate the generated site: every internal link resolves, no page is orphaned,
no thought is duplicated, and every thought carries a real attribution."""

import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")
DATA = os.path.join(ROOT, "data")

problems = []
notes = []


def resolve(href):
    """Map a site URL onto the file that would be served for it."""
    href = href.split("#")[0].split("?")[0]
    if not href.startswith("/"):
        return None
    p = os.path.join(OUT, href.lstrip("/"))
    if os.path.isdir(p):
        p = os.path.join(p, "index.html")
    elif not os.path.splitext(p)[1]:
        p = p + "/index.html" if os.path.isdir(p[: p.rfind("/")]) else p
        p = os.path.join(OUT, href.lstrip("/"), "index.html")
    return p


# ---- 1. every internal link resolves to a file that exists
pages = []
for dirpath, _, files in os.walk(OUT):
    for f in files:
        if f.endswith(".html"):
            pages.append(os.path.join(dirpath, f))

linked = set()
for page in pages:
    html = open(page, encoding="utf-8").read()
    rel = os.path.relpath(page, OUT)
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
            continue
        target = resolve(href)
        if target is None:
            continue
        linked.add(os.path.relpath(target, OUT))
        if not os.path.exists(target):
            problems.append("%s -> dead link %s" % (rel, href))

# ---- 2. no orphaned pages (nothing links to them)
for page in pages:
    rel = os.path.relpath(page, OUT)
    if rel in ("index.html", "404.html"):
        continue
    if rel not in linked:
        problems.append("orphan page, nothing links to it: /%s" % rel[: -len("/index.html")])

# ---- 3. data integrity
with open(os.path.join(DATA, "thoughts.json"), encoding="utf-8") as f:
    thoughts = json.load(f)["thoughts"]

seen = Counter()
for i, t in enumerate(thoughts, 1):
    key = " ".join(re.sub(r"[^a-z0-9 ]", "", t["text"].lower()).split()[:9])
    seen[key] += 1
    if not t.get("author", "").strip():
        problems.append("thought %d has no author" % i)
    if not t.get("source", "").strip():
        problems.append("thought %d (%s) has no source" % (i, t.get("author")))
    if len(t["text"]) > 320:
        problems.append("thought %d (%s) is %d chars — too long" % (i, t["author"], len(t["text"])))
    if t["text"].strip()[:1] in ('"', "“"):
        problems.append("thought %d (%s) is wrapped in quote marks" % (i, t["author"]))
    if t.get("contributor") is not None and not str(t.get("contributor", "")).strip():
        problems.append("thought %d has an empty contributor field" % i)

for key, n in seen.items():
    if n > 1:
        problems.append("duplicated quote (%dx): %s…" % (n, key[:50]))

# ---- 4. attribution coverage
no_url = [t for t in thoughts if not (t.get("source_url") or "").strip()]
authors = Counter(t["author"] for t in thoughts)
# folk labels are collective, not individuals — they are allowed to lead
PROVERB = re.compile(r"\b(proverb|saying|folk)\b", re.I)
people = Counter({a: n for a, n in authors.items() if not PROVERB.search(a)})
top, topn = people.most_common(1)[0] if people else ("", 0)

origs = sum(1 for t in thoughts if (t.get("original") or "").strip())
notes.append("%d thoughts, %d authors, %d sources, %d contributors"
             % (len(thoughts), len(authors), len({t["source"] for t in thoughts}),
                len({(t.get("contributor") or "StartupThoughts") for t in thoughts})))
notes.append("%d carry the original-language line" % origs)
notes.append("%d/%d have a source URL" % (len(thoughts) - len(no_url), len(thoughts)))
notes.append("most-quoted person: %s (%d)" % (top, topn))
notes.append("folk voices: " + ", ".join("%s (%d)" % kv for kv in
             sorted(((a, n) for a, n in authors.items() if PROVERB.search(a)),
                    key=lambda kv: -kv[1])[:7]))
notes.append("%d html pages generated" % len(pages))

if len(thoughts) >= 40 and topn > len(thoughts) * 0.15:
    problems.append("%s dominates the collection (%d of %d)" % (top, topn, len(thoughts)))

# ---- report
for n in notes:
    print("  " + n)
if problems:
    print("\n%d problem(s):" % len(problems))
    for p in problems[:40]:
        print("  ! " + p)
    if len(problems) > 40:
        print("  … and %d more" % (len(problems) - 40))
    sys.exit(1)
print("\nall checks passed")
