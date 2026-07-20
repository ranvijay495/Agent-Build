"""Generates DASHBOARD.md from jobs.db after each sweep. GitHub renders it natively."""
import sqlite3, os, datetime

DB = os.environ.get("DB_PATH", "jobs.db")
STATUS_ORDER = ["queued", "manual", "new", "scored", "applied", "interview", "skipped", "rejected"]
EMOJI = {"queued": "🟢", "manual": "🟠", "applied": "✅", "interview": "🎯",
         "skipped": "⚪", "rejected": "❌", "new": "🔵", "scored": "🔵"}

def build():
    c = sqlite3.connect(DB)
    rows = c.execute("""SELECT company,title,location,portal,url,posted_date,
                        status,score,cv_choice,first_seen FROM jobs
                        ORDER BY posted_date DESC""").fetchall()
    counts = {}
    for r in rows:
        counts[r[6]] = counts.get(r[6], 0) + 1
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M UTC")

    md = [f"# Job Pipeline Dashboard\n",
          f"_Last sweep: {now} · {len(rows)} roles tracked_\n",
          "## Funnel\n",
          "| " + " | ".join(s.capitalize() for s in STATUS_ORDER) + " |",
          "|" + "---|" * len(STATUS_ORDER),
          "| " + " | ".join(str(counts.get(s, 0)) for s in STATUS_ORDER) + " |\n"]

    for status in STATUS_ORDER:
        group = [r for r in rows if r[6] == status]
        if not group:
            continue
        md.append(f"## {EMOJI.get(status,'')} {status.capitalize()} ({len(group)})\n")
        md.append("| Role | Company | Location | Portal | Posted | Score | CV | Link |")
        md.append("|---|---|---|---|---|---|---|---|")
        for r in group:
            link = f"[Apply]({r[4]})" if r[4] else "-"
            md.append(f"| {r[1]} | {r[0]} | {r[2]} | {r[3]} | {r[5]} | "
                      f"{r[7] if r[7] is not None else '-'} | {r[8] or '-'} | {link} |")
        md.append("")

    with open("DASHBOARD.md", "w") as f:
        f.write("\n".join(md))
    print(f"Dashboard written: {len(rows)} roles")

if __name__ == "__main__":
    build()
