#!/usr/bin/env python3
"""Pull only the fact-checked quotes out of a workflow run.

A run's journal holds the raw gather output alongside the verified output,
with no labels to tell them apart. Merging it wholesale would re-admit every
quote the fact-checkers rejected, so identify the checkers by their prompt.

    python3 extract.py <workflow-dir> [out.json]
"""
import glob, json, os, sys

def main():
    d = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "verified.json"

    kind = {}
    for f in glob.glob(os.path.join(d, "agent-*.jsonl")):
        aid = os.path.basename(f)[6:-6]
        head = open(f, encoding="utf-8", errors="replace").read(6000)
        kind[aid] = "verify" if "Adversarial" in head else "gather"

    quotes, seen = [], set()
    for line in open(os.path.join(d, "journal.jsonl"), encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "result":
            continue
        res = r.get("result") or {}
        if "quotes" in res and kind.get(r.get("agentId")) == "verify":
            for q in res["quotes"]:
                k = " ".join(str(q.get("text", "")).lower().split()[:8])
                if k and k not in seen:
                    seen.add(k)
                    quotes.append(q)

    json.dump({"thoughts": quotes}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    nv = sum(1 for k in kind.values() if k == "verify")
    print("%d verify batches, %d verified quotes -> %s" % (nv, len(quotes), out))

if __name__ == "__main__":
    main()
