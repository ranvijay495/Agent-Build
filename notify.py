"""Telegram notifications: cards with a working Open-posting button, digest, and dashboard file."""
import json, os, urllib.request

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API = f"https://api.telegram.org/bot{TOKEN}"

def _post(method, payload):
    req = urllib.request.Request(f"{API}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception as e:
        print(f"Telegram {method} failed: {e}")
        return False

def send_card(jid, job, verdict):
    text = (f"{job['title']} — {job['company']}\n"
            f"{job['location']} | {job['portal']} | posted {job['posted_date']}\n"
            f"Score {verdict['relevance_score']} | CV: {verdict['cv_choice']}\n\n"
            f"Why: {verdict['why']}\n"
            f"Flags: {', '.join(verdict.get('red_flags') or ['none'])}\n\n"
            f"Cover letter:\n{verdict['cover_letter']}")
    payload = {"chat_id": CHAT_ID, "text": text[:4000]}
    if job.get("url"):
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "Open posting", "url": job["url"]}]]}
    _post("sendMessage", payload)

def send_digest(n_new, n_queued):
    _post("sendMessage", {"chat_id": CHAT_ID,
        "text": f"Job sweep done: {n_new} new roles, {n_queued} worth your review. Dashboard attached next."})

def send_document(path, caption=""):
    import uuid
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{CHAT_ID}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
            f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: text/html\r\n\r\n").encode() \
           + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{API}/sendDocument", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"sendDocument failed: {e}")
