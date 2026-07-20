"""Reads LinkedIn job-alert emails from Gmail (read-only) and returns job dicts."""
import base64, json, os, re, urllib.parse, urllib.request

def _token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"],
        "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["access_token"]

def _get(url, tok):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def _plaintext(payload):
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="ignore")
    for p in payload.get("parts", []) or []:
        t = _plaintext(p)
        if t: return t
    return ""

NOISE = re.compile(r"(actively hiring|school alum|connection|apply with|your job alert|^\W*$)", re.I)

def poll_linkedin(days=2):
    try:
        tok = _token()
    except Exception as e:
        print(f"Gmail auth failed: {e}")
        return []
    q = urllib.parse.quote(f"from:jobalerts-noreply@linkedin.com newer_than:{days}d")
    base = "https://gmail.googleapis.com/gmail/v1/users/me"
    try:
        msgs = _get(f"{base}/messages?q={q}&maxResults=25", tok).get("messages", [])
    except Exception as e:
        print(f"Gmail list failed: {e}")
        return []
    out, seen = [], set()
    for m in msgs:
        try:
            full = _get(f"{base}/messages/{m['id']}?format=full", tok)
        except Exception:
            continue
        text = _plaintext(full.get("payload", {}))
        ts = int(full.get("internalDate", "0")) // 1000
        import datetime
        ds = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
        for mt in re.finditer(r"([^\n]{3,90})\n([^\n]{2,60})\n([^\n]{2,60})\nView job: (https://\S+)", text):
            title, company, loc, url = (g.strip() for g in mt.groups())
            if NOISE.search(title) or NOISE.search(company): continue
            if "mumbai" in loc.lower(): continue
            key = title + company
            if key in seen: continue
            seen.add(key)
            out.append({"company": company, "title": title, "location": loc,
                        "portal": "LinkedIn", "url": url.split("?")[0],
                        "posted_date": ds, "date_confidence": "email-dated"})
    print(f"LinkedIn parser: {len(out)} roles from {len(msgs)} alert emails")
    return out
