"""Builds dashboard.html from jobs.db and sends it to Telegram after each sweep."""
import sqlite3, os, datetime
import notify

DB = os.environ.get("DB_PATH", "jobs.db")
ORDER = ["queued", "manual", "applied", "interview", "new", "scored", "skipped", "rejected"]
COLORS = {"queued": "#16a34a", "manual": "#d97706", "applied": "#2563eb",
          "interview": "#7c3aed", "skipped": "#9ca3af", "rejected": "#dc2626",
          "new": "#0891b2", "scored": "#0891b2"}

def build():
    c = sqlite3.connect(DB)
    rows = c.execute("""SELECT company,title,location,portal,url,posted_date,status,score,cv_choice
                        FROM jobs ORDER BY posted_date DESC""").fetchall()
    counts = {}
    for r in rows:
        counts[r[6]] = counts.get(r[6], 0) + 1
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M UTC")

    kpis = "".join(
        f"<div class='kpi' style='border-top:3px solid {COLORS.get(s,'#888')}'>"
        f"<div class='n'>{counts[s]}</div><div class='l'>{s}</div></div>"
        for s in ORDER if counts.get(s))

    sections = []
    for s in ORDER:
        group = [r for r in rows if r[6] == s]
        if not group:
            continue
        cards = "".join(
            f"<a class='card' href='{r[4] or '#'}' target='_blank'>"
            f"<div class='t'>{r[1]}</div>"
            f"<div class='m'>{r[0]} · {r[2]}</div>"
            f"<div class='b'><span class='pill'>{r[3]}</span>"
            f"<span>{r[5]}</span>"
            f"<span>{('score ' + str(r[7])) if r[7] is not None else ''}</span>"
            f"<span>{r[8] or ''}</span></div></a>"
            for r in group)
        sections.append(f"<h2 style='color:{COLORS.get(s,'#888')}'>{s.capitalize()} "
                        f"({len(group)})</h2><div class='grid'>{cards}</div>")

    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Job Pipeline</title><style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f5f7;margin:0;padding:16px;color:#1f2937}}
h1{{font-size:20px;margin:0 0 2px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:16px}}
h2{{font-size:15px;margin:22px 0 10px;text-transform:capitalize}}
.kpis{{display:flex;gap:10px;flex-wrap:wrap}}
.kpi{{background:#fff;border-radius:10px;padding:10px 16px;box-shadow:0 1px 3px rgba(0,0,0,.08);min-width:70px;text-align:center}}
.kpi .n{{font-size:22px;font-weight:700}} .kpi .l{{font-size:11px;color:#6b7280;text-transform:capitalize}}
.grid{{display:grid;gap:10px}}
.card{{background:#fff;border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.08);text-decoration:none;color:inherit;display:block}}
.card .t{{font-weight:600;font-size:14px}} .card .m{{color:#374151;font-size:13px;margin:2px 0 6px}}
.card .b{{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#6b7280;align-items:center}}
.pill{{background:#eef2ff;color:#4338ca;border-radius:5px;padding:1px 7px;font-weight:600}}
</style></head><body>
<h1>Job Pipeline</h1><div class='sub'>Last sweep: {now} · {len(rows)} roles tracked · tap any card to open the posting</div>
<div class='kpis'>{kpis}</div>{''.join(sections)}</body></html>"""

    with open("dashboard.html", "w") as f:
        f.write(html)
    print(f"Dashboard written: {len(rows)} roles")
    notify.send_document("dashboard.html", caption="Your pipeline after today's sweep")

if __name__ == "__main__":
    build()
