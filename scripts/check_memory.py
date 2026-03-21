import json
from collections import Counter
from pathlib import Path

lines = Path("memory/memory.jsonl").read_text(encoding="utf-8").splitlines()
all_entries = [json.loads(l) for l in lines if l.strip()]
accepted = [e for e in all_entries if e.get("decision") == "accepted"]
sigs = [e["bug_signature"] for e in accepted]

print("Total runs    :", len(all_entries))
print("Total accepted:", len(accepted))
print()
print("Top signatures:")
for sig, count in Counter(sigs).most_common(5):
    print(" ", count, "x", sig)
print()
print("Last 3 entries:")
for e in all_entries[-3:]:
    print(" ", e["decision"], "|", e["failure_category"], "|", e.get("repo", ""))
