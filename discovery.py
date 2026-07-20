"""Discovery worker v2: Greenhouse/Lever/Ashby boards from config/watchlist.csv
PLUS Oracle Recruiting Cloud tenants (Gulf heavyweights) with exact posted dates."""
import csv, json, datetime, urllib.request, urllib.parse, ssl, socket

socket.setdefaulttimeout(15)
CTX = ssl.create_default_context()
KEYWORDS = ["strategy","corporate development","chief of staff","m&a","merger","founder",
            "ceo office","office of the ceo","investor relations","corp dev","transformation",
            "special projects","ventures","investments","corporate finance","business planning",
            "corporate planning"]
MAX_AGE_DAYS = 60
INCLUDE_LOC = ["india","bengaluru","bangalore","gurgaon","gurugram","noida","delhi","hyderabad","chennai",
               "pune","kerala","remote","dubai","abu dhabi","uae","united arab emirates","riyadh","saudi",
               "doha","qatar","kuwait","bahrain","muscat","oman"]
EXCLUDE_LOC = ["mumbai","navi mumbai"]

# Oracle Recruiting Cloud tenants: (company, host, siteNumber)
ORACLE_TENANTS = [
    ("DP World", "ehpv.fa.em2.oraclecloud.com", "CX_1"),
    ("AD Ports Group", "fa-ewzx-saasfaprod1.fa.ocs.oraclecloud.com", "CX_1"),
    ("Emirates NBD", "fa-evlo-saasfaprod1.fa.ocs.oraclecloud.com", "CX_1"),
    ("FAB", "ehjd.fa.em2.oraclecloud.com", "CX_1"),
]
ORACLE_QUERIES = ["strategy", "corporate development", "chief of staff", "M&A", "investor relations"]

def _get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def _kw(title): return any(k in title.lower() for k in KEYWORDS)

def _loc_ok(loc):
    import re as _re
    l = loc.lower()
    inc = any(_re.search(r"\b" + _re.escape(x) + r"\b", l) for x in INCLUDE_LOC)
    exc = any(_re.search(r"\b" + _re.escape(x) + r"\b", l) for x in EXCLUDE_LOC)
    return inc and not exc

def _fresh(dt):
    return dt >= datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=MAX_AGE_DAYS)

def poll_oracle():
    out, seen = [], set()
    for company, host, site in ORACLE_TENANTS:
        for q in ORACLE_QUERIES:
            finder = (f"findReqs;siteNumber={site},"
                      f"facetsList=LOCATIONS%3BWORK_LOCATIONS%3BWORKPLACE_TYPES%3BTITLES%3BCATEGORIES%3BORGANIZATIONS%3BPOSTING_DATES%3BFLEX_FIELDS,"
                      f"limit=25,keyword={urllib.parse.quote(q)},sortBy=POSTING_DATES_DESC")
            url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                   f"?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values&finder={finder}")
            d = _get(url)
            if not d or not d.get("items"): continue
            for r in d["items"][0].get("requisitionList", []):
                title = r.get("Title", "")
                loc = r.get("PrimaryLocation", "") or ""
                key = company + title + loc
                if key in seen: continue
                seen.add(key)
                if not (_kw(title) and _loc_ok(loc)): continue
                try:
                    dt = datetime.datetime.fromisoformat(r.get("PostedDate", "")).replace(
                        tzinfo=datetime.timezone.utc)
                    if not _fresh(dt): continue
                    ds = dt.strftime("%Y-%m-%d")
                except Exception:
                    ds = "unknown"
                req_id = r.get("Id", "")
                job_url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{req_id}"
                out.append({"company": company, "title": title, "location": loc, "portal": "Oracle",
                            "url": job_url, "posted_date": ds, "date_confidence": "verified"})
    return out


# Workday CXS tenants: (company, tenant, wd_datacenter, site)
WORKDAY_TENANTS = [
    ("Adobe", "adobe", "wd5", "external_experienced"),
    ("S&P Global", "spgi", "wd5", "SPGI_Careers"),
    ("Salesforce", "salesforce", "wd12", "External_Career_Site"),
]
WORKDAY_QUERIES = ["corporate strategy India", "corporate development India", "chief of staff India", "strategy Bengaluru", "strategy Gurgaon", "strategy Noida", "M&A India"]

def _wd_age_days(posted_on):
    p = (posted_on or "").lower()
    if "today" in p: return 0
    if "yesterday" in p: return 1
    if "30+" in p: return 999
    m = __import__("re").search(r"(\d+)\s+days", p)
    return int(m.group(1)) if m else 999

def poll_workday():
    out, seen = [], set()
    for company, tenant, wd, site in WORKDAY_TENANTS:
        base = f"https://{tenant}.{wd}.myworkdayjobs.com"
        for q in WORKDAY_QUERIES:
            body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).encode()
            url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
            try:
                req = urllib.request.Request(url, data=body, headers={
                    "User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
                    "Accept": "application/json"})
                with urllib.request.urlopen(req, context=CTX) as r:
                    d = json.loads(r.read().decode())
            except Exception:
                continue
            for j in d.get("jobPostings", []):
                title = j.get("title", "")
                loc = j.get("locationsText", "") or ""
                key = company + title + loc
                if key in seen: continue
                seen.add(key)
                if not (_kw(title) and _loc_ok(loc)): continue
                age = _wd_age_days(j.get("postedOn", ""))
                if age > MAX_AGE_DAYS: continue
                ds = (datetime.datetime.now(datetime.timezone.utc)
                      - datetime.timedelta(days=age)).strftime("%Y-%m-%d")
                out.append({"company": company, "title": title, "location": loc, "portal": "Workday",
                            "url": base + "/en-US/" + site + j.get("externalPath", ""),
                            "posted_date": ds, "date_confidence": "verified"})
    return out


# Workday tenants: (company, tenant, wd_dc, site)
WORKDAY_TENANTS = [
    ("PwC", "pwc", "wd3", "Global_Experienced_Careers"),
    ("Mastercard", "mastercard", "wd1", "CorporateCareers"),
    ("Salesforce", "salesforce", "wd12", "External_Career_Site"),
    ("Adobe", "adobe", "wd5", "external_experienced"),
    ("NVIDIA", "nvidia", "wd5", "NVIDIAExternalCareerSite"),
    ("PayPal", "paypal", "wd1", "jobs"),
]
WORKDAY_QUERIES = ["corporate development", "strategy", "chief of staff", "M&A"]

def _wd_days(posted):
    p = (posted or "").lower()
    if "today" in p: return 0
    if "yesterday" in p: return 1
    if "30+" in p: return 999
    m = [int(s) for s in p.split() if s.isdigit()]
    return m[0] if m else 999

def poll_workday():
    out, seen = [], set()
    for company, tenant, wd, site in WORKDAY_TENANTS:
        for q in WORKDAY_QUERIES:
            url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).encode()
            try:
                req = urllib.request.Request(url, data=body, headers={
                    "User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
                    "Accept": "application/json"})
                with urllib.request.urlopen(req, context=CTX) as r:
                    d = json.loads(r.read().decode())
            except Exception:
                continue
            for j in d.get("jobPostings", []):
                title = j.get("title", "")
                loc = j.get("locationsText", "") or ""
                key = company + title + loc
                if key in seen: continue
                seen.add(key)
                if not (_kw(title) and _loc_ok(loc)): continue
                days = _wd_days(j.get("postedOn", ""))
                if days > MAX_AGE_DAYS: continue
                ds = (datetime.datetime.now(datetime.timezone.utc)
                      - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
                path = j.get("externalPath", "")
                job_url = f"https://{tenant}.{wd}.myworkdayjobs.com/en-US/{site}{path}"
                out.append({"company": company, "title": title, "location": loc, "portal": "Workday",
                            "url": job_url, "posted_date": ds, "date_confidence": "verified"})
    return out

def poll_boards(watchlist_path="config/watchlist.csv"):
    out = []
    with open(watchlist_path) as f:
        for row in csv.DictReader(f):
            if not str(row.get("status", "")).startswith("LIVE"): continue
            ats, slug, company = row["ats"], row["slug_or_tenant"], row["company"]
            if ats == "greenhouse":
                d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
                for j in (d or {}).get("jobs", []):
                    t, loc = j.get("title", ""), (j.get("location") or {}).get("name", "") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    try:
                        dt = datetime.datetime.fromisoformat((j.get("updated_at") or "").replace("Z", "+00:00"))
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    except Exception: ds = "unknown"
                    out.append({"company": company, "title": t, "location": loc, "portal": "Greenhouse",
                                "url": j.get("absolute_url", ""), "posted_date": ds, "date_confidence": "verified"})
            elif ats == "lever":
                d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
                for j in (d if isinstance(d, list) else []):
                    t, loc = j.get("text", ""), (j.get("categories") or {}).get("location", "") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    ts = j.get("createdAt")
                    if ts:
                        dt = datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc)
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    else: ds = "unknown"
                    out.append({"company": company, "title": t, "location": loc, "portal": "Lever",
                                "url": j.get("hostedUrl", ""), "posted_date": ds, "date_confidence": "verified"})
            elif ats == "ashby":
                d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
                for j in (d or {}).get("jobs", []):
                    t, loc = j.get("title", ""), j.get("location", "") or ""
                    if not (_kw(t) and _loc_ok(loc)): continue
                    try:
                        dt = datetime.datetime.fromisoformat((j.get("publishedAt") or "").replace("Z", "+00:00"))
                        if not _fresh(dt): continue
                        ds = dt.strftime("%Y-%m-%d")
                    except Exception: ds = "unknown"
                    out.append({"company": company, "title": t, "location": loc, "portal": "Ashby",
                                "url": j.get("jobUrl", ""), "posted_date": ds, "date_confidence": "verified"})
    return out

def poll_all(watchlist_path="config/watchlist.csv"):
    return poll_boards(watchlist_path) + poll_oracle() + poll_workday() + poll_workday()
