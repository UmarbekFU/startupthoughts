#!/usr/bin/env python3
"""Add a thought. The easy path.

    python3 add.py                          ask me the questions
    python3 add.py --json '{"text": ...}'   paste what the /add page gave you
    pbpaste | python3 add.py -              take it from the clipboard
    python3 add.py --json '...' --push      ...and deploy it

Appends to data/thoughts.json, rebuilds the site, and validates. Existing ids
are never touched, so live links keep pointing at the same thought.
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
THOUGHTS = os.path.join(DATA, "thoughts.json")
MAX_LEN = 300

FIELDS = [
    ("text",        "the thought", True),
    ("original",    "the original, if not said in English (enter to skip)", False),
    ("author",      "who said it", True),
    ("source",      "where they said it (essay, book, talk, interview)", True),
    ("source_url",  "a link to it (enter to skip)", False),
    ("contributor", "your name, for the leaderboard", True),
]


def die(msg):
    sys.exit("\n  %s\n" % msg)


def load():
    with open(THOUGHTS, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("thoughts", raw) if isinstance(raw, dict) else raw


def strip_wrapping(s):
    s = s.strip()
    while len(s) > 2 and s[0] in '"“«‘' and s[-1] in '"”»’':
        s = s[1:-1].strip()
    return s


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", "", s.lower()).split()[:9])


def validate(e, existing):
    missing = [k for k in ("text", "author", "source", "contributor")
               if not str(e.get(k, "")).strip()]
    if missing:
        die("still needed: " + ", ".join(missing))
    if len(e["text"]) > MAX_LEN:
        die("that is %d characters. A thought has to fit in %d — trim it to the "
            "sentence that carries the idea." % (len(e["text"]), MAX_LEN))
    if len(e["text"]) < 12:
        die("that is too short to be a thought.")
    if re.search(r"\b(proverb|saying|folk|anonymous|unknown|traditional)\b",
                 e["author"], re.I):
        die("every thought here is by a named person. “%s” is not a name."
            % e["author"])
    key = norm(e["text"])
    for t in existing:
        if norm(t["text"]) == key:
            die("already here as /t/%d, added by %s."
                % (t.get("id", 0), t.get("contributor", "?")))


def ask():
    print("\n  Adding a thought. One rule: a real person really said it, and you "
          "know where.\n")
    e = {}
    for key, prompt, required in FIELDS:
        while True:
            v = input("  %s\n  > " % prompt).strip()
            print()
            if v or not required:
                e[key] = v
                break
            print("  ...that one is required.\n")
    return e


def read_json(src):
    try:
        e = json.loads(src)
    except ValueError as exc:
        die("that is not valid JSON (%s)" % exc)
    if not isinstance(e, dict):
        die("expected a single JSON object")
    return e


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT).returncode


def main():
    args = sys.argv[1:]
    push = "--push" in args
    args = [a for a in args if a != "--push"]

    if args and args[0] == "--json":
        if len(args) < 2:
            die("--json needs the JSON after it")
        entry = read_json(args[1])
    elif args and args[0] == "-":
        entry = read_json(sys.stdin.read())
    elif args:
        die("unknown option %r — see the top of this file" % args[0])
    else:
        entry = ask()

    existing = load()

    e = {
        "text": strip_wrapping(str(entry.get("text", ""))),
        "author": strip_wrapping(str(entry.get("author", ""))),
        "source": strip_wrapping(str(entry.get("source", ""))),
        "source_url": str(entry.get("source_url", "") or "").strip(),
        "contributor": strip_wrapping(str(entry.get("contributor", ""))),
    }
    orig = strip_wrapping(str(entry.get("original", "") or ""))
    if orig:
        e["original"] = orig
        if entry.get("original_lang"):
            e["original_lang"] = str(entry["original_lang"]).strip()

    validate(e, existing)
    e["id"] = max([t.get("id", 0) for t in existing] or [0]) + 1

    existing.append(e)
    with open(THOUGHTS, "w", encoding="utf-8") as f:
        json.dump({"thoughts": existing}, f, ensure_ascii=False, indent=1)

    print("  added as /t/%d\n" % e["id"])

    if run([sys.executable, "build.py"]) != 0:
        die("build failed — data/thoughts.json has been written, fix and rebuild")
    if run([sys.executable, "check.py"]) != 0:
        die("validation failed — see above")

    # where the contributor now stands (the seed collection does not compete)
    try:
        curator = json.load(open(os.path.join(DATA, "config.json"),
                                 encoding="utf-8")).get("curator", "StartupThoughts")
    except (IOError, ValueError):
        curator = "StartupThoughts"

    counts = {}
    for t in existing:
        who = t.get("contributor") or curator
        if who == curator:
            continue
        counts[who] = counts.get(who, 0) + 1

    me = e["contributor"]
    if me == curator:
        return
    board = sorted(counts.items(), key=lambda kv: -kv[1])
    rank = [n for n, _ in board].index(me) + 1
    print("\n  %s: %d thought%s \u2014 rank %d of %d"
          % (me, counts[me], "" if counts[me] == 1 else "s", rank, len(board)))
    ahead = [(n, c) for n, c in board if c > counts[me]]
    if ahead:
        n, c = ahead[-1]
        print("  %d more to pass %s" % (c - counts[me] + 1, n))
    else:
        print("  that is first place. Somebody will come for it.")

    if push:
        print()
        run(["git", "add", "-A"])
        run(["git", "commit", "-q", "-m",
             "add: %s — %s" % (e["author"], e["text"][:60])])
        if run(["git", "push", "-q"]) == 0:
            print("\n  pushed. Vercel is deploying it now.")
    else:
        print("\n  to publish:  git add -A && git commit -m 'new thought' && git push")


if __name__ == "__main__":
    main()
