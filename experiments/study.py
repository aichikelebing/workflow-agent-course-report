"""Run the DBLP–ACM field-acquisition study. Python 3.9+, standard library."""
import argparse
import csv
import hashlib
import html
import io
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
FIELDS = ("authors", "year", "venue")
SEED = 20261119


def norm(x):
    x = unicodedata.normalize("NFKD", html.unescape(str(x)).lower())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in x if not unicodedata.combining(c))))


def words(x):
    return set(norm(x).split())


def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a or b else 0.0


def author_names(x):
    parts = re.split(r",|;|\band\b", html.unescape(x))
    return {tokens[-1] for part in parts if (tokens := norm(part).split())}


def venue_key(x):
    s = norm(x)
    if "sigmod record" in s or "sigmod record" in s.replace("special interest group on management of data", "sigmod"):
        return "sigmod-record"
    if "sigmod" in s or "conference on management of data" in s:
        return "sigmod-conf"
    if "vldb" in s or "large data base" in s or "large database" in s:
        return "vldb-journal" if "journal" in s else "vldb-conf"
    return s


def title_sim(p):
    return dice(words(p["left"]["title"]), words(p["right"]["title"]))


def evidence(p, field, masked=False):
    a, b = p["left"][field], p["right"][field]
    if field == "authors" and masked:
        b = ""
    return [a, b]


def contribution(field, a, b):
    if not a.strip() or not b.strip():
        return 0.0
    if field == "authors":
        return .32 * (2 * dice(author_names(a), author_names(b)) - 1)
    if field == "year":
        return .12 if a == b else -.22
    return .10 if venue_key(a) == venue_key(b) else -.15


def margin(p, seen, masked=False):
    return title_sim(p) - .78 + sum(contribution(f, *evidence(p, f, masked)) for f in seen)


def judge(p, seen, masked=False):
    return int(margin(p, seen, masked) >= 0)


def baseline(p, group, masked=False, forced_author=False):
    seen = ["authors"] if forced_author else []
    if not seen:
        if group == "B" and abs(margin(p, [])) >= .25:
            return []
        seen.append("authors")
    if group == "A":
        return seen + ["year"]
    if abs(margin(p, seen, masked)) >= .18:
        return seen
    a, b = evidence(p, "authors", masked)
    return seen + (["venue"] if not a or not b else ["year"])


def save(name, obj):
    OUT.mkdir(exist_ok=True)
    if name.endswith(".jsonl"):
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in obj)
    else:
        content = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    (OUT / name).write_text(content, encoding="utf-8")


def load(name):
    content = (OUT / name).read_text(encoding="utf-8")
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in content.splitlines()]
    return json.loads(content)


def source_table(path):
    data = path.read_bytes()
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raw = data.decode("latin-1")
    return list(csv.DictReader(io.StringIO(raw)))


def pairs_from_sources(folder):
    left = {r["id"]: r for r in source_table(folder / "DBLP2.csv")}
    right = {r["id"]: r for r in source_table(folder / "ACM.csv")}
    gold = {(r["idDBLP"], r["idACM"]) for r in source_table(folder / "DBLP-ACM_perfectMapping.csv")}
    # Assign whole connected components of the bipartite gold graph to one split.
    components = {}
    def rep(x):
        components.setdefault(x, x)
        while x != components[x]:
            components[x] = components[components[x]]
            x = components[x]
        return x
    for a, b in sorted(gold):
        ra, rb = rep("L"+a), rep("R"+b)
        components[max(ra, rb)] = min(ra, rb)
    def split(key):
        value = hashlib.sha256((str(SEED) + rep(key)).encode()).digest()[0]
        return "dev" if value < 64 else "test"
    result = []
    rng = random.Random(SEED)
    for part, per_bin in [("dev", 2), ("test", 8)]:
        left_ok = {k for k in left if split("L"+k) == part}
        right_ok = {k for k in right if split("R"+k) == part}
        ltok = {k: words(left[k]["title"]) for k in sorted(left_ok)}
        rtok = {k: words(right[k]["title"]) for k in sorted(right_ok)}
        index = defaultdict(set)
        for k, tokens in rtok.items():
            for t in tokens:
                index[t].add(k)
        positives = sorted((dice(ltok[a], rtok[b]), a, b) for a,b in gold if a in left_ok)
        negatives = []
        for a, tokens in ltok.items():
            candidates = set()
            for t in tokens:
                if len(index[t]) <= 100:
                    candidates.update(index[t])
            matches = [(dice(tokens, rtok[b]), b) for b in candidates if (a,b) not in gold]
            if matches:
                score, b = max(matches)
                negatives.append((score,a,b))
        negatives.sort(reverse=True)
        used_entities = set()
        selected = []
        for label, pool in [(1, positives), (0, negatives)]:
            boundary = len(pool) // 5
            for difficulty, subset in [("hard", pool[:boundary]), ("remaining", pool[boundary:])]:
                rng.shuffle(subset)
                n = 0
                for score,a,b in subset:
                    entities = {rep("L"+a), rep("R"+b)}
                    if used_entities & entities:
                        continue
                    used_entities.update(entities)
                    selected.append(dict(left=left[a],right=right[b],label=label,split=part,stratum=difficulty))
                    n += 1
                    if n == per_bin:
                        break
                assert n == per_bin
        rng.shuffle(selected)
        for i,p in enumerate(selected,1):
            p["case"] = ("D" if part == "dev" else "T") + f"{i:02d}"
            result.append(p)
    return result


def blind(p, seen, masked=False, key=None):
    return dict(case=key or p["case"], titles=[p["left"]["title"],p["right"]["title"]],
                observed={f:evidence(p,f,masked) for f in seen},
                actions=[f for f in FIELDS if f not in seen] + ["stop"])


def read_actions(path, requests):
    actions = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(actions) != {r["case"] for r in requests}:
        raise ValueError("Action keys do not match blind case IDs")
    for r in requests:
        if actions[r["case"]] not in r["actions"]:
            raise ValueError(f"Illegal action for {r['case']}")
    return actions


def paired_cases(test):
    # Rank by title ambiguity under the fixed judge. Require complete authors so
    # that suppressing the ACM author field changes exactly one observation.
    eligible = [p for p in test if all(evidence(p,"authors"))]
    return sorted(eligible,key=lambda p:(abs(margin(p,[])),p["case"]))[:8]


def blind_key(case, prefix):
    return prefix + hashlib.sha256((prefix + "/" + case).encode()).hexdigest()[:6]


def present(p, path, group, masked=False, variant="original"):
    pred = judge(p,path,masked)
    return dict(case=p["case"], group=group, variant=variant, actions=path,
                observations={f: evidence(p, f, masked) for f in path},
                gold=p["label"], prediction=pred, correct=pred==p["label"],
                margin=round(margin(p,path,masked),6), queries=len(path))


def metrics(rows):
    counts = Counter((r["gold"],r["prediction"]) for r in rows)
    tp,fp,fn,tn = (counts[k] for k in [(1,1),(0,1),(1,0),(0,0)])
    return dict(n=len(rows),tp=tp,fp=fp,fn=fn,tn=tn,
                f1=round(2*tp/(2*tp+fp+fn),4) if (2*tp+fp+fn) else 0,
                accuracy=round((tp+tn)/len(rows),4),
                field_queries=sum(r["queries"] for r in rows),
                controller_decisions=sum(r.get("controller_decisions",0) for r in rows),
                avg_queries=round(sum(r["queries"] for r in rows)/len(rows),4))


def prepare(folder):
    manifest=pairs_from_sources(folder)
    save("cases.json",manifest)
    test=[p for p in manifest if p["split"]=="test"]
    save("blind-first.jsonl",[blind(p,[]) for p in test])
    paired=paired_cases(test)
    # Different case IDs for the independently blinded masked condition.
    save("blind-masked.jsonl",sorted([blind(p,["authors"],True,blind_key(p["case"],"M")) for p in paired],key=lambda r:r["case"]))
    save("blind-original.jsonl",sorted([blind(p,["authors"],False,blind_key(p["case"],"O")) for p in paired],key=lambda r:r["case"]))
    print("Prepared",len(test),"test and",len(manifest)-len(test),"development pairs.")


def second():
    test=[p for p in load("cases.json") if p["split"]=="test"]
    first=read_actions(OUT/"actions-first.json",load("blind-first.jsonl"))
    save("blind-second.jsonl",[blind(p,[first[p["case"]]]) for p in test if first[p["case"]]!="stop"])


def score():
    manifest=load("cases.json")
    test=[p for p in manifest if p["split"]=="test"]
    first=read_actions(OUT/"actions-first.json",load("blind-first.jsonl"))
    second=read_actions(OUT/"actions-second.json",load("blind-second.jsonl"))
    main=[]
    for p in test:
        key=p["case"]
        model=[a for a in [first[key],second.get(key,"stop")] if a!="stop"]
        for g,path in [("A",baseline(p,"A")),("B",baseline(p,"B")),("C",model)]:
            main.append(present(p,path,g))
    for r in main:
        r["controller_decisions"] = (1 + int(first[r["case"]] != "stop")) if r["group"] == "C" else 0
    save("main-traces.json",main)
    save("main-summary.json",{g:metrics([r for r in main if r["group"]==g]) for g in "ABC"})
    dev=[p for p in manifest if p["split"]=="dev"]
    save("dev-summary.json",{g:metrics([present(p,baseline(p,g),g) for p in dev]) for g in "AB"})
    paired=paired_cases(test)
    replays=[]
    detail=[]
    for variant,prefix,mask in [("original","O",False),("masked","M",True)]:
        decisions=read_actions(OUT/f"actions-{variant}.json",load(f"blind-{variant}.jsonl"))
        for i,p in enumerate(paired,1):
            act=decisions[blind_key(p["case"],prefix)]
            paths={"A":baseline(p,"A",mask,True),"B":baseline(p,"B",mask,True),
                   "C":["authors"]+([] if act=="stop" else [act])}
            for g,path in paths.items():
                row = present(p,path,g,mask,variant)
                row["controller_decisions"] = int(g == "C")
                detail.append(row)
            for act in ["stop","year","venue"]:
                path=["authors"]+([] if act=="stop" else [act])
                replays.append(present(p,path,act,mask,variant))
    save("paired-traces.json",detail)
    save("paired-replay.json",replays)
    save("paired-summary.json",{v:{g:metrics([r for r in detail if r["variant"]==v and r["group"]==g]) for g in "ABC"} for v in ("original","masked")})


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["prepare","second","score"])
    parser.add_argument("--data",type=Path)
    args=parser.parse_args()
    if args.stage=="prepare":
        if not args.data:
            parser.error("--data must point to the three CSVs")
        prepare(args.data)
    elif args.stage=="second":
        second()
    else:
        score()
