"""Telegram approval flow: sends one card per queued job with Approve/Skip buttons.
Wire the callback handling into your existing PA bot (it already long-polls/webhooks)."""
import json, os, urllib.request, urllib.parse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API = f"https://api.telegram.org/bot{TOKEN}"

def send_card(jid, job, verdict):
    text = (f"*{job['title']}* at *{job['company']}*\n"
            f"{job['location']} | {job['portal']} | posted {job['posted_date']}\n"
            f"Score: {verdict['relevance_score']} | CV: {verdict['cv_choice']}\n"
            f"Why: {verdict['why']}\n"
            f"Flags: {', '.join(verdict.get('red_flags') or ['none'])}\n"
            f"[Posting]({job['url']})\n\n"
            f"_Cover letter:_\n{verdict['cover_letter'][:600]}")
    kb = {"inline_keyboard": [[
        {"text": "Approve", "callback_data": f"approve:{jid}"},
        {"text": "Skip", "callback_data": f"skip:{jid}"},
        {"text": "Manual", "callback_data": f"manual:{jid}"}]]}
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown",
                                   "reply_markup": json.dumps(kb)}).encode()
    urllib.request.urlopen(urllib.request.Request(f"{API}/sendMessage", data=data))

def send_digest(n_new, n_queued):
    msg = f"Job sweep done: {n_new} new roles found, {n_queued} above threshold sent for approval."
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
    urllib.request.urlopen(urllib.request.Request(f"{API}/sendMessage", data=data))
