import json, sys, collections, statistics as st, pathlib
D = pathlib.Path(__file__).resolve().parent
r = json.loads((D / f"results_{sys.argv[1]}.json").read_text(encoding="utf-8"))
for who in ("local", "groq"):
    rows = r[who]
    for s in ("history", "new", "multi"):
        rr = [x for x in rows if x["set"] == s]
        if not rr:
            continue
        oc = collections.Counter(x["outcome"] for x in rr)
        print(who, s, f"{oc['ok']}/{len(rr)}", dict(oc), "lat", round(st.mean(x["latency_s"] for x in rr), 2))
        for x in rr:
            if x["outcome"] != "ok":
                print("   X", x["id"], x["text"][:40], "| exp", x["expected"], "got", x["got"])
if len(sys.argv) > 2:
    for x in r["local"]:
        if "args" in x:
            a = x["args"]
            print(x["id"], x["rep"], x["text"][:30], "->", a["tool"], json.dumps(a["arguments"], ensure_ascii=False)[:120], "ok" if a["schema_ok"] else "SCHEMA-FAIL", a["latency_s"])
