"""Reads job-alert emails from Gmail (read-only) across multiple senders and
returns job dicts. Uses Claude (same provider config as score.py) to extract
structured jobs from each email, so no per-sender regex is needed.
Falls back to the LinkedIn regex parser if the LLM call fails."""
import base64, datetime, json, os, re, urllib.parse, urllib.request

# Senders to sweep. Add a tuple ("email-or-domain-fragment", "Portal label") to onboard a new source.
SENDERS = [
    ("jobalerts-noreply@linkedin.com", "LinkedIn"),
    ("noreply@mail.michaelpage.co.in", "MichaelPage"),
    ("EYJobAlerts@noreply12.jobs2web.com", "EY-Careers"),
    ("donotreply@email.careers.microsoft.com", "Microsoft"),
    ("team@hi.wellfound.com", "Wellfound"),
    ("jj@myworkday.com", "Workday-JnJ"),
]

EXTRACT_SYSTEM = """You extract job postings from job-alert emails.
Given the raw text of one email, return ONLY a JSON array (no prose, no markdown fences).
Each element: {"title": "...", "company": "...", "location": "..."}
Rules:
- Only include actual job postings advertised in the email. Ignore navigation text,
  footers, unsubscribe links, application-status updates, and promotional content.
- If the email is from a recruiting agency (e.g. Michael Page) and the client company
  is not named, use the agency name as company.
- If a field is genuinely absent, use "" for it.
- If the email contains no job postings, return []."""


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


def _llm(user_content):
    """Same provider selection as score.py, but with the extraction system prompt."""
    provider = os.environ.get("PROVIDER", "anthropic").lower()
    if provider == "bedrock":
        import boto3
        client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2000,
                           "system": EXTRACT_SYSTEM,
                           "messages": [{"role": "user", "content": user_content}]})
        resp = client.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"], body=body,
                                   contentType="application/json", accept="application/json")
        data = json.loads(resp["body"].read())
    else:
        body = json.dumps({"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
                           "max_tokens": 2000, "system": EXTRACT_SYSTEM,
                           "messages": [{"role": "user", "content": user_content}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "Content-Type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _extract_jobs(text):
    """LLM extraction: email text in, list of {title, company, location} out."""
    # Strip long tracking URLs to save tokens; keep everything else verbatim.
    slim = re.sub(r"https?://\S{60,}", "[link]", text)[:9000]
    raw = _llm(f"Email text:\n\n{slim}").strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    jobs = json.loads(raw)
    return jobs if isinstance(jobs, list) else []


# --- LinkedIn regex fallback (used only if the LLM call fails) ---
NOISE = re.compile(r"(actively hiring|school alum|connection|apply with|your job alert|^\W*$)", re.I)
BADGE = re.compile(r"^(fast growing|actively recruiting|be an early applicant|promoted|easy apply|remote|hybrid|on-site|new|\d+\s+applicants?.*|response rate.*|posted \d+.*)$", re.I)

def _linkedin_regex(text):
    out = []
    for mt in re.finditer(r"((?:[^\n]+\n){2,6}?)View job: (https://\S+)", text):
        block = mt.group(1)
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        lines = [l for l in lines if not (NOISE.search(l) or BADGE.match(l))][-3:]
        if len(lines) < 2: continue
        if "\u00b7" in lines[-1]:
            company, _, loc = (p.strip() for p in lines[-1].partition("\u00b7"))
            title = lines[-2]
        elif len(lines) == 3:
            title, company, loc = lines
        else:
            title, company = lines; loc = ""
        out.append({"title": title, "company": company, "location": loc})
    return out


def poll_all_senders(days=2):
    try:
        tok = _token()
    except Exception as e:
        print(f"Gmail auth failed: {e}")
        return []
    base = "https://gmail.googleapis.com/gmail/v1/users/me"
    out, seen, email_count = [], set(), 0
    for sender, portal in SENDERS:
        q = urllib.parse.quote(f"from:{sender} newer_than:{days}d")
        try:
            msgs = _get(f"{base}/messages?q={q}&maxResults=15", tok).get("messages", [])
        except Exception as e:
            print(f"Gmail list failed for {portal}: {e}")
            continue
        email_count += len(msgs)
        for m in msgs:
            try:
                full = _get(f"{base}/messages/{m['id']}?format=full", tok)
            except Exception:
                continue
            text = _plaintext(full.get("payload", {}))
            if not text.strip(): continue
            ts = int(full.get("internalDate", "0")) // 1000
            ds = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
            try:
                jobs = _extract_jobs(text)
            except Exception as e:
                print(f"LLM extraction failed for {portal} email: {e}")
                jobs = _linkedin_regex(text) if portal == "LinkedIn" else []
            for j in jobs:
                title = (j.get("title") or "").strip()
                company = (j.get("company") or "").strip()
                loc = (j.get("location") or "").strip()
                if not title or not company: continue
                if "mumbai" in f"{title} {company} {loc}".lower(): continue
                key = (title + company).lower()
                if key in seen: continue
                seen.add(key)
                out.append({"company": company, "title": title, "location": loc,
                            "portal": portal, "url": f"https://mail.google.com/mail/u/0/#all/{m['id']}",
                            "posted_date": ds, "date_confidence": "email-dated"})
    print(f"Email parser: {len(out)} roles from {email_count} alert emails across {len(SENDERS)} senders")
    return out


# Backwards-compatible entry point (main.py calls poll_linkedin)
def poll_linkedin(days=2):
    return poll_all_senders(days)
