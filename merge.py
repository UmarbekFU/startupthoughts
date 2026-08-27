#!/usr/bin/env python3
"""Merge the research workflow output into data/thoughts.json.

Reads every workflow journal under the session's subagents directory, pools the
quotes, then cleans the pool: drop duplicates, drop anything unsourced or
over-long, stop any one voice from dominating, and interleave so that /new does
not read as one batch after another.

    python3 merge.py [extra-journal-or-json ...]
"""

import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
SESSION = os.path.expanduser(
    "~/.claude/projects/-Users-umar-Desktop-StartupThoughts/"
    "3b37473b-55ce-4ed8-8458-52838b5ad8c3/subagents/workflows"
)

MAX_LEN = 300          # a thought, not a passage
MAX_PER_PERSON = 12          # no individual may swamp the collection
PROVERB = re.compile(r"\b(proverb|saying|folk)\b", re.I)


def fold(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def undash(s):
    """No dashes in quotes. A comma carries a parenthetical clause fine."""
    s = re.sub(r"\s*[\u2014\u2013]\s*$", "", s)          # trailing dash: just drop it
    s = re.sub(r"\s+[\u2014\u2013]\s+", ", ", s)          # spaced: becomes a comma
    s = re.sub(r"(?<=\w)[\u2014\u2013](?=\w)", ", ", s)   # tight: same
    s = re.sub(r"\s*[\u2014\u2013]\s*", ", ", s)          # anything left
    return re.sub(r",\s*,", ",", s)


def strip_wrapping(s):
    s = s.strip()
    while len(s) > 2 and s[0] in '"“«‘' and s[-1] in '"”»’':
        s = s[1:-1].strip()
    return s


def collect(paths):
    """Pull every quote object out of workflow journals and plain json files."""
    pool = []
    for path in paths:
        if path.endswith(".jsonl"):
            for line in open(path, encoding="utf-8"):
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                res = rec.get("result")
                if isinstance(res, dict) and isinstance(res.get("quotes"), list):
                    pool += res["quotes"]
                elif isinstance(res, dict) and isinstance(res.get("batches"), list):
                    for b in res["batches"]:
                        pool += b.get("quotes", []) or []
        else:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("thoughts", raw) if isinstance(raw, dict) else raw
            pool += items
    return pool


def clean(pool):
    seen, kept = {}, []
    stats = Counter()

    for q in pool:
        if not isinstance(q, dict):
            continue
        text = undash(strip_wrapping(str(q.get("text") or "")))
        author = str(q.get("author") or "").strip()
        source = str(q.get("source") or "").strip()

        if not text or not author:
            stats["no text or author"] += 1
            continue
        # folk sayings are out: every thought is by a named person
        if PROVERB.search(author) or author.lower() in ("unknown", "anonymous", "traditional"):
            stats["folk / unattributed"] += 1
            continue
        if len(text) > MAX_LEN:
            stats["too long"] += 1
            continue
        if len(text) < 12:
            stats["too short"] += 1
            continue
        if not source:
            source = "traditional" if PROVERB.search(author) else ""
            if not source:
                stats["no source"] += 1
                continue
        # a named living person with a shaky attribution is the one thing we
        # cannot publish; folk sayings carry no such risk
        if q.get("confidence") == "low" and not PROVERB.search(author):
            stats["low confidence"] += 1
            continue

        key = " ".join(fold(text).split()[:9])
        if key in seen:
            stats["duplicate"] += 1
            # keep whichever has the better provenance
            if q.get("source_url") and not seen[key].get("source_url"):
                seen[key]["source_url"] = q["source_url"]
            continue

        entry = {
            "text": text,
            "author": author,
            "source": source,
            "source_url": str(q.get("source_url") or "").strip(),
        }
        orig = strip_wrapping(str(q.get("original") or ""))
        if orig and fold(orig) != fold(text):
            entry["original"] = orig
        seen[key] = entry
        kept.append(entry)

    # no single voice may swamp the collection
    per = defaultdict(int)
    capped = []
    for e in kept:
        per[e["author"]] += 1
        if per[e["author"]] <= MAX_PER_PERSON:
            capped.append(e)
        else:
            stats["over per-person cap"] += 1

    return capped, stats


def interleave(entries):
    """Round-robin by author so neighbouring thoughts do not repeat a voice."""
    buckets = defaultdict(list)
    for e in entries:
        buckets[e["author"]].append(e)
    order = sorted(buckets, key=lambda a: (-len(buckets[a]), a))
    out, live = [], True
    while live:
        live = False
        for a in order:
            if buckets[a]:
                out.append(buckets[a].pop(0))
                live = True
    return out


def load_existing():
    """Whatever is already published. Its ids are permanent — they are live URLs."""
    path = os.path.join(DATA, "thoughts.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("thoughts", raw) if isinstance(raw, dict) else raw


def main():
    paths = sys.argv[1:]
    if not paths:
        paths = sorted(glob.glob(os.path.join(SESSION, "*", "journal.jsonl")))
    if not paths:
        sys.exit("no workflow journals found — pass paths explicitly")

    existing = load_existing()
    print("reading %d file(s); %d thoughts already published" % (len(paths), len(existing)))

    pool = collect(paths)
    print("  %d raw quotes from research" % len(pool))

    fresh, stats = clean(pool)

    # never re-publish something already here, and never renumber what is
    # already here: /t/12 must always be the same thought.
    have = {" ".join(fold(e["text"]).split()[:9]) for e in existing}
    added = [e for e in fresh if " ".join(fold(e["text"]).split()[:9]) not in have]
    stats["already published"] = len(fresh) - len(added)

    for reason, n in stats.most_common():
        if n:
            print("  dropped %-22s %d" % (reason, n))

    next_id = max([e.get("id", 0) for e in existing] or [0]) + 1
    for e in interleave(added):
        e["id"] = next_id
        next_id += 1

    entries = existing + added

    out = os.path.join(DATA, "thoughts.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"thoughts": entries}, f, ensure_ascii=False, indent=1)

    authors = Counter(e["author"] for e in entries)
    print("\n  added %d new, %d thoughts total" % (len(added), len(entries)))
    print("  %d authors, %d sources, %d with an original-language line"
          % (len(authors), len({e["source"] for e in entries}),
             sum(1 for e in entries if e.get("original"))))
    print("  top voices: " + ", ".join("%s (%d)" % kv for kv in authors.most_common(6)))
    print("  -> %s" % out)


if __name__ == "__main__":
    main()
