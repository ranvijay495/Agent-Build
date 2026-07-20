"""Scoring brain: one Claude call per new job. Chooses CV, drafts cover letter + screener answers.
Supports two providers, selected by env var PROVIDER:
  PROVIDER=bedrock    -> Claude via Amazon Bedrock (pays with your AWS credits)
  PROVIDER=anthropic  -> Claude via Anthropic API directly (default)
"""
import json, os, urllib.request

PROVIDER = os.environ.get("PROVIDER", "anthropic").lower()
ANSWERS = json.load(open("config/answers.json"))

PROFILE = """Ranvijay Singh. Director - Corporate Development and Strategy / Chief of Staff to Chairman & CEO,
MPS Limited (BSE/NSE listed, ~USD 450M mcap), Noida. Led company's largest acquisition (Unbound Medicine, USD 16.5M)
end to end: diligence, SPA negotiation, ~USD 1M indemnity adjustments, post-merger integration with ~USD 5M synergies,
EBITDA 15% to 30%. Built CorpDev function from scratch: 4-member team, 50+ targets screened, 10+ LOIs (incl. German
carve-out via GmbH Newco with 80/20 earnout; re-cut a media-services deal to BTA after finding fabricated WIP).
Owns earnings presentations, investor deck, MD&A of Annual Report; engaged 20+ institutional investors for QIP.
Turnarounds: reversed 40% YoY revenue decline to +8% in 5 months; ~USD 1M annual cloud savings; led AWS-to-GCP migration.
ISB PGP (Dean's List). BITS Pilani B.Tech Marine Engineering (topper). 4 years marine engineering officer,
Northern Marine Management UK on LNG tankers ($25M overhaul projects). Builds production AI tools (Python, Node, Claude API)."""

SYSTEM = f"""You score job postings for this candidate and prepare application drafts.
CANDIDATE PROFILE: {PROFILE}
STANDARD ANSWERS: {json.dumps({k: v for k, v in ANSWERS.items() if k != "cv_files"})}
RULES:
- Mumbai-based roles: score 0, red-flag them.
- Roles clearly below Director/AVP/Senior-Manager band: score under 40.
- cv_choice: "corpdev_ma" for M&A/CorpDev/IR/strategy-finance roles; "chief_of_staff" for CoS/CEO-office/founder-office/ops-strategy roles.
- Cover letters: blunt, specific, plain English, grounded in the profile facts, 150-200 words, no em dashes, no AI-generic phrasing.
- Gulf roles: mention visa sponsorship need only if the form asks; expected package answer is "0" (negotiable signal).
Respond ONLY with JSON: {{"relevance_score": 0-100, "cv_choice": "...", "why": "...", "cover_letter": "...",
"screener_answers": {{"notice_period": "...", "expected_compensation": "...", "why_this_company": "..."}}, "red_flags": []}}"""


def _call_anthropic(user_content):
    body = json.dumps({
        "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"), "max_tokens": 1200,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user_content}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "Content-Type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")


def _call_bedrock(user_content):
    import boto3  # provided via requirements.txt
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 1200,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user_content}],
    })
    resp = client.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"], body=body,
                               contentType="application/json", accept="application/json")
    data = json.loads(resp["body"].read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def score_job(job):
    user_content = f"Job posting:\n{json.dumps(job)}"
    text = _call_bedrock(user_content) if PROVIDER == "bedrock" else _call_anthropic(user_content)
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)
