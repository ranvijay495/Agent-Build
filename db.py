"""SQLite state store: dedupe + application funnel tracking."""
import sqlite3, hashlib, os

DB = os.environ.get("DB_PATH", "jobs.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,          -- hash(company+title)
  company TEXT, title TEXT, location TEXT,
  portal TEXT, url TEXT, posted_date TEXT, date_confidence TEXT,
  status TEXT DEFAULT 'new',    -- new|scored|queued|skipped|applied|manual|interview|rejected
  score INTEGER, cv_choice TEXT, why TEXT,
  cover_letter TEXT, screener_answers TEXT, red_flags TEXT,
  first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
  last_update TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def conn():
    c = sqlite3.connect(DB); c.execute(SCHEMA); return c

def job_id(company, title):
    return hashlib.sha1(f"{company.lower().strip()}|{title.lower().strip()}".encode()).hexdigest()[:16]

def upsert_new(c, rec):
    """Insert if unseen. Returns True if new."""
    jid = job_id(rec["company"], rec["title"])
    cur = c.execute("SELECT 1 FROM jobs WHERE id=?", (jid,))
    if cur.fetchone(): return False
    c.execute("INSERT INTO jobs (id,company,title,location,portal,url,posted_date,date_confidence) VALUES (?,?,?,?,?,?,?,?)",
              (jid, rec["company"], rec["title"], rec["location"], rec["portal"], rec["url"], rec["posted_date"], rec.get("date_confidence","verified")))
    c.commit(); return True

def set_score(c, jid, score, cv, why, letter, answers, flags):
    c.execute("UPDATE jobs SET status='scored',score=?,cv_choice=?,why=?,cover_letter=?,screener_answers=?,red_flags=?,last_update=CURRENT_TIMESTAMP WHERE id=?",
              (score, cv, why, letter, answers, flags, jid))
    c.commit()

def set_status(c, jid, status):
    c.execute("UPDATE jobs SET status=?,last_update=CURRENT_TIMESTAMP WHERE id=?", (status, jid)); c.commit()
