"""Daily entrypoint: discover (boards + Oracle + Workday + LinkedIn emails) -> dedupe -> score -> notify."""
import json, os
import db, discovery, score, notify

THRESHOLD = 65

def run():
    c = db.conn()
    found = discovery.poll_all()
    if os.environ.get("GMAIL_REFRESH_TOKEN"):
        import gmail_parser
        found += gmail_parser.poll_linkedin()
    new_jobs = [j for j in found if db.upsert_new(c, j)]
    queued = 0
    for job in new_jobs:
        jid = db.job_id(job["company"], job["title"])
        try:
            v = score.score_job(job)
        except Exception as e:
            print(f"score failed for {jid}: {e}"); continue
        db.set_score(c, jid, v["relevance_score"], v["cv_choice"], v["why"],
                     v["cover_letter"], json.dumps(v["screener_answers"]), json.dumps(v.get("red_flags", [])))
        if v["relevance_score"] >= THRESHOLD and not v.get("red_flags"):
            db.set_status(c, jid, "queued")
            notify.send_card(jid, job, v)
            queued += 1
        else:
            db.set_status(c, jid, "skipped")
    notify.send_digest(len(new_jobs), queued)
    print(f"Done: {len(found)} matches, {len(new_jobs)} new, {queued} queued")

if __name__ == "__main__":
    run()
