#!/usr/bin/env python3
"""Remove thoughts an audit flagged as off-topic.

    python3 prune.py            show what would go
    python3 prune.py --apply    remove them

Reads the "drop" lists produced by the prune workflow and deletes those ids.
Ids of surviving thoughts are never changed, so live links keep working.
"""
import glob, json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
JOURNALS = os.path.join(
    os.path.expanduser("~/.claude/projects/-Users-umar-Desktop-StartupThoughts"),
    "*", "subagents", "workflows", "*", "journal.jsonl")


def main():
    apply = "--apply" in sys.argv
    drops = {}
    for path in glob.glob(JOURNALS):
        for line in open(path, encoding="utf-8"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            res = rec.get("result")
            if isinstance(res, dict) and isinstance(res.get("drop"), list):
                for d in res["drop"]:
                    if isinstance(d, dict) and "id" in d:
                        drops[d["id"]] = d.get("reason", "")

    p = os.path.join(ROOT, "data", "thoughts.json")
    data = json.load(open(p, encoding="utf-8"))
    thoughts = data["thoughts"]
    hit = [t for t in thoughts if t["id"] in drops]

    print("%d flagged, %d of them present in the collection of %d"
          % (len(drops), len(hit), len(thoughts)))
    if hit:
        print("\nby author:")
        for a, n in Counter(t["author"] for t in hit).most_common():
            print("  %-26s %d" % (a, n))

    if not apply:
        print("\n(dry run — pass --apply to remove them)")
        return

    keep = [t for t in thoughts if t["id"] not in drops]
    data["thoughts"] = keep
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nremoved %d, %d remain" % (len(hit), len(keep)))


if __name__ == "__main__":
    main()
