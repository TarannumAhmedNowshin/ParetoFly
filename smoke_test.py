import json, urllib.request, os, glob

body = json.dumps({
    "origin": "Dhaka",
    "destination": "Dublin",
    "depart_date": "2026-09-02",
    "adults": 1,
    "cabin": "economy",
    "currency": "USD",
    "is_student": True,
    "free_text": "daytime arrival preferred, no red-eyes",
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/search",
    data=body,
    headers={"Content-Type": "application/json"},
)
d = json.load(urllib.request.urlopen(req, timeout=300))

print("SESSION", d["session_id"], flush=True)
print("ERROR", d["error"], flush=True)
print("RECS", len(d["recommendations"]), flush=True)
for r in d["recommendations"]:
    o = r["scored"]["offer"]
    price = o.get("true_price") or o["price"]
    print(f"\n#{r['rank']} {', '.join(o['airlines'])} | {o['currency']} {price:.0f} | score {r['scored']['total_score']:.3f}", flush=True)
    print(f"   dep {o['segments'][0]['departure_time']} -> arr {o['segments'][-1]['arrival_time']} | stops {len(o['segments'])-1}", flush=True)
    print(f"   student_disc={o.get('student_discount_amount')} site_disc={o.get('site_discount_amount')} bag_kg={o.get('baggage_allowance_kg')}", flush=True)
    print(f"   PROS {r['pros']}", flush=True)
    print(f"   CONS {r['cons']}", flush=True)

sid = d["session_id"]
path = os.path.join("reports", f"{sid}_report.md")
print("\nREPORT EXISTS:", os.path.exists(path), path, flush=True)
print("ALL REPORTS:", glob.glob("reports/*.md"), flush=True)
if os.path.exists(path):
    print("\n===== REPORT CONTENT =====\n", flush=True)
    print(open(path, encoding="utf-8").read(), flush=True)

