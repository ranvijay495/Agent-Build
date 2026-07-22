"""Daily entrypoint: discover (boards + Oracle + Workday + LinkedIn emails) -> dedupe -> score -> notify."""
import json, os
import db, discovery, score, notify

THRESHOLD = 65

def run():
    c = db.conn()
    # TEMP: purge unscored LinkedIn rows garbled by the old parser; they re-import
    # cleanly from the 2-day email window. Safe to remove once scores are flowing.
    c.execute("DELETE FROM jobs WHERE portal='LinkedIn' AND score IS NULL"); c.commit()
    found = discovery.poll_all()
    if os.environ.get("GMAIL_REFRESH_TOKEN"):
        import gmail_parser
        found += gmail_parser.poll_linkedin()
    new_jobs = [j for j in found if db.upsert_new(c, j)]
    # Retry jobs that were inserted earlier but never scored (e.g. past API failures)
    fields = ("company", "title", "location", "portal", "url", "posted_date")
    rows = c.execute(f"SELECT {','.join(fields)} FROM jobs WHERE status='new' AND score IS NULL").fetchall()
    fresh_ids = {db.job_id(j["company"], j["title"]) for j in new_jobs}
    retries = [dict(zip(fields, r)) for r in rows
               if db.job_id(r[0], r[1]) not in fresh_ids]
    if retries:
        print(f"Retrying {len(retries)} previously unscored jobs")
    queued = 0
    failures = []
    for job in new_jobs + retries:
        jid = db.job_id(job["company"], job["title"])
        try:
            v = score.score_job(job)
        except Exception as e:
            print(f"score failed for {jid}: {e}")
            failures.append(f"{type(e).__name__}: {e}")
            continue
        db.set_score(c, jid, v["relevance_score"], v["cv_choice"], v["why"],
                     v["cover_letter"], json.dumps(v["screener_answers"]), json.dumps(v.get("red_flags", [])))
        if v["relevance_score"] >= THRESHOLD and not v.get("red_flags"):
            db.set_status(c, jid, "queued")
            notify.send_card(jid, job, v)
            queued += 1
        else:
            db.set_status(c, jid, "skipped")
    if failures:
        notify.send_message(f"WARNING: scoring failed for {len(failures)} job(s). "
                            f"First error: {failures[0][:500]}\n"
                            f"Check PROVIDER / BEDROCK_MODEL_ID / AWS secrets in repo settings.")
    notify.send_digest(len(new_jobs), queued)
    print(f"Done: {len(found)} matches, {len(new_jobs)} new, {queued} queued, {len(failures)} score failures")

if __name__ == "__main__":
    run()
