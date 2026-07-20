"""Processes Telegram button taps: Approve / Switch CV / Skip. Runs on its own schedule."""
import json, os, sqlite3, urllib.request

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
DB = os.environ.get("DB_PATH", "jobs.db")

def _api(method, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def run():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    row = c.execute("SELECT v FROM kv WHERE k='tg_offset'").fetchone()
    offset = int(row[0]) if row else 0
    try:
        upd = _api("getUpdates", {"offset": offset + 1, "timeout": 0,
                                  "allowed_updates": ["callback_query"]})
    except Exception as e:
        print(f"getUpdates failed: {e}"); return
    handled = 0
    for u in upd.get("result", []):
        offset = max(offset, u["update_id"])
        cq = u.get("callback_query")
        if not cq: continue
        action, _, jid = (cq.get("data") or "").partition(":")
        job = c.execute("SELECT title, company, cv_choice FROM jobs WHERE id=?", (jid,)).fetchone()
        if not job:
            _api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Job not found"})
            continue
        title, company, cv = job
        if action == "approve":
            c.execute("UPDATE jobs SET status='approved', last_update=CURRENT_TIMESTAMP WHERE id=?", (jid,))
            msg = f"Approved: {title} at {company} (CV: {cv}). Auto-apply comes in phase 2 — open and apply for now."
        elif action == "skip":
            c.execute("UPDATE jobs SET status='skipped', last_update=CURRENT_TIMESTAMP WHERE id=?", (jid,))
            msg = f"Skipped: {title} at {company}."
        elif action == "cvswap":
            new_cv = "chief_of_staff" if cv == "corpdev_ma" else "corpdev_ma"
            c.execute("UPDATE jobs SET cv_choice=?, last_update=CURRENT_TIMESTAMP WHERE id=?", (new_cv, jid))
            msg = f"CV switched to {new_cv} for {title} at {company}."
        else:
            continue
        _api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Done"})
        _api("sendMessage", {"chat_id": cq["message"]["chat"]["id"], "text": msg})
        handled += 1
    c.execute("INSERT INTO kv (k, v) VALUES ('tg_offset', ?) "
              "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(offset),))
    c.commit()
    print(f"Listener: {handled} taps processed")

if __name__ == "__main__":
    run()
