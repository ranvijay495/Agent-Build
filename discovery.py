"""Discovery worker: polls Greenhouse/Lever/Ashby boards from config/watchlist.csv.
Only rows with status starting LIVE are polled. Enforces 60-day freshness and location rules."""
import csv, json, datetime, urllib.request, ssl, socket

socket.setdefaulttimeout(15)
CTX = ssl.create_default_context()
KEYWORDS = ["strategy","corporate development","chief of staff","m&a","merger","founder","ceo office",
            "office of the ceo","investor relations","corp dev","transformation","special projects",
            "ventures","investments","corporate finance"]
MAX_AGE_DAYS = 60
INCLUDE_LOC = ["india","bengaluru","bangalore","gurgaon","gurugram","noida","delhi","hyderabad","chennai",
               "pune","remote","dubai","abu dhabi","uae","united arab emirates","riyadh","saudi","doha",
               "qatar","kuwait","bahrain","muscat","oman"]
EXCLUDE_LOC = ["mumbai","navi mumbai"]

def _get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def _kw(title): return any(k in title.lower() for k in KEYWORDS)

def _loc_ok(loc):
    l = loc.lower()
    return any(x in l for x in INCLUDE_LOC) and not any(x in l for x in EXCLUDE_LOC)

def _fresh(dt):
    return dt >= datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=MAX_AGE_DAYS)

def poll_all(watchlist_path="config/watchlist.csv"):
    out = []
    with open(watchlist_path) as f:
        for row in csv.DictReader(f):
            if not str(row.get("status","")).startswith("LIVE"): continue
            ats, slug, company = row["ats"], row["slug_or_tenant"], row["company"]
            if ats == "greenhouse":
                d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
                for j in (d or {}).get("jobs", []):
                    t, loc = j.get("title",""), (j.get("location") or {}).get("name","") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    try:
                        dt = datetime.datetime.fromisoformat((j.get("updated_at") or "").replace("Z","+00:00"))
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    except Exception: ds = "unknown"
                    out.append({"company":company,"title":t,"location":loc,"portal":"Greenhouse",
                                "url":j.get("absolute_url",""),"posted_date":ds,"date_confidence":"verified"})
            elif ats == "lever":
                d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
                for j in (d if isinstance(d,list) else []):
                    t, loc = j.get("text",""), (j.get("categories") or {}).get("location","") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    ts = j.get("createdAt")
                    if ts:
                        dt = datetime.datetime.fromtimestamp(ts/1000, datetime.timezone.utc)
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    else: ds = "unknown"
                    out.append({"company":company,"title":t,"location":loc,"portal":"Lever",
                                "url":j.get("hostedUrl",""),"posted_date":ds,"date_confidence":"verified"})
            elif ats == "ashby":
                d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
                for j in (d or {}).get("jobs", []):
                    t, loc = j.get("title",""), j.get("location","") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    try:
                        dt = datetime.datetime.fromisoformat((j.get("publishedAt") or "").replace("Z","+00:00"))
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    except Exception: ds = "unknown"
                    out.append({"company":company,"title":t,"location":loc,"portal":"Ashby",
                                "url":j.get("jobUrl",""),"posted_date":ds,"date_confidence":"verified"})
    return out
