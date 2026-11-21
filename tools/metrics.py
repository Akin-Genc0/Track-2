"""The metrics the judges report (brief, section 6), measured on labelled sets.
Usage: python3 tools/metrics.py <predictions.jsonl> <labels.jsonl> [<predictions> <labels> ...] [--md]
Labels are practice_labels.jsonl or a shadow set's shadow_labels.jsonl (both carry hit_id and decision).
A hit missing from the predictions counts as REVIEW, as in tools/score.py."""
import json, sys

COST = {("DIFFERENT_ENTITY", "SAME_ENTITY"): 3, ("DIFFERENT_ENTITY", "REVIEW"): 3,
        ("SAME_ENTITY", "DIFFERENT_ENTITY"): 60, ("SAME_ENTITY", "REVIEW"): 2,
        ("REVIEW", "DIFFERENT_ENTITY"): 60, ("REVIEW", "SAME_ENTITY"): 2}


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def metrics(pred_path, label_path):
    pred = {r["hit_id"]: r["decision"] for r in load(pred_path)}
    pairs = [(L["decision"], pred.get(L["hit_id"], "REVIEW")) for L in load(label_path)]
    n = len(pairs)
    cleared = [t for t, d in pairs if d == "DIFFERENT_ENTITY"]
    false_pos = [d for t, d in pairs if t == "DIFFERENT_ENTITY"]
    same = [d for t, d in pairs if t == "SAME_ENTITY"]
    cost = sum(COST.get(p, 0) for p in pairs)
    base = sum(COST.get((t, "REVIEW"), 0) for t, _ in pairs)
    ratio = lambda a, b: a / b if b else None
    return {
        "hits": n,
        "right": sum(t == d for t, d in pairs),
        # a clear of a true match or of a hit the policy leaves for review: the 60-point error
        "unsafe_clearances": sum(t != "DIFFERENT_ENTITY" for t in cleared),
        "false_positives_cleared": ratio(sum(d == "DIFFERENT_ENTITY" for d in false_pos), len(false_pos)),
        "false_positives": len(false_pos),
        "clearance_precision": ratio(sum(t == "DIFFERENT_ENTITY" for t in cleared), len(cleared)),
        "clears": len(cleared),
        "same_entity_recall": ratio(sum(d == "SAME_ENTITY" for d in same), len(same)),
        "same_entities": len(same),
        "review_rate": ratio(sum(d == "REVIEW" for _, d in pairs), n),
        "decision_score": max(0.0, 1 - cost / base) if base else None,
        "cost": cost, "all_review_cost": base,
    }


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def main(argv):
    md = "--md" in argv
    args = [a for a in argv if a != "--md"]
    if not args or len(args) % 2:
        sys.exit(__doc__)
    rows = [(p, l, metrics(p, l)) for p, l in zip(args[::2], args[1::2])]
    if md:
        print("| Set | Hits | Unsafe clearances | False positives cleared | Clearance precision | Same-entity recall | Review rate | Decision score |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for p, l, m in rows:
        if md:
            print(f"| {l} | {m['hits']} | {m['unsafe_clearances']} | {pct(m['false_positives_cleared'])} ({m['false_positives']} FPs) "
                  f"| {pct(m['clearance_precision'])} ({m['clears']} clears) | {pct(m['same_entity_recall'])} ({m['same_entities']} matches) "
                  f"| {pct(m['review_rate'])} | {m['decision_score']:.3f} |")
        else:
            print(json.dumps(dict(predictions=p, labels=l, **m)))


if __name__ == "__main__":
    main(sys.argv[1:])
