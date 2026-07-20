# Job Agent v1 - Discovery + Scoring + Telegram Approval

## What this does (daily)
1. Polls every LIVE endpoint in config/watchlist.csv (Greenhouse/Lever/Ashby public APIs)
2. Filters: keyword match, India+Gulf locations, Mumbai excluded, hard 60-day freshness
3. Dedupes against SQLite (jobs.db)
4. Scores each new role via Claude API: relevance, CV choice, cover letter, screener answers
5. Sends roles scoring 65+ to your Telegram with Approve / Skip / Manual buttons

## Setup (15 min)
1. `pip install -r requirements.txt` (stdlib only - the file exists for Railway detection)
2. Copy the two CV PDFs into `cvs/` with the exact filenames in config/answers.json
3. `cp .env.example .env` and fill in keys (Anthropic key, your existing PA bot token + chat id)
4. Test locally: `python main.py`
5. Deploy to Railway; add a cron schedule `0 6 * * *` (daily 6am) running `python main.py`
6. In your PA bot, handle callback_data `approve:{id}`, `skip:{id}`, `manual:{id}` and call
   db.set_status accordingly (approve -> 'applied' once the executor exists; for now 'queued').

## What's deliberately NOT here (phase 2)
- Playwright executor for Greenhouse/Lever forms (fires on Approve). Build only after a week
  of reviewing what the scorer queues - tune THRESHOLD in main.py first.
- Puppeteer pollers for Naukri/Bayt/Naukrigulf/GulfTalent (bot-walled; needs your residential-fingerprint setup)
- Gmail parser for LinkedIn alert emails (Claude adds this in-chat; port the logic here after)
- Workday/Oracle connectors (needs per-tenant config - ask Claude to run the Workday config batch)

## Hard rules encoded
- 60-day freshness enforced in discovery.py (MAX_AGE_DAYS)
- Mumbai excluded in discovery.py and re-checked by the scorer
- Nothing is ever submitted without your Approve tap
- No LinkedIn/Indeed automation. Ever.

## Free deployment: GitHub Actions (no Railway needed)
1. Create a PRIVATE repo on github.com and upload this whole folder (including the hidden .github folder)
2. Repo Settings -> Secrets and variables -> Actions -> New repository secret. Add three:
   ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
3. That's it. The workflow in .github/workflows/daily.yml runs every morning at 6:30 AM IST.
   Test immediately: repo -> Actions tab -> "Daily job sweep" -> "Run workflow" button.
4. The database (jobs.db) is committed back to the repo after each run so duplicates never resend.
Note: GitHub's scheduler can start runs 5-15 minutes late during busy hours. Irrelevant for a daily job sweep.

## Using your AWS credits instead (Amazon Bedrock)
Your $500 AWS credits can pay for the Claude calls. One-time setup on your PERSONAL AWS account:
1. AWS Console -> Amazon Bedrock (switch region to us-east-1) -> Model access -> request access
   to Anthropic Claude models (approval is usually instant).
2. On the same Model access / Models page, copy the exact "Inference profile ID" for the newest
   Claude Sonnet model - it looks like us.anthropic.claude-sonnet-... Save it.
3. IAM -> Users -> Create user (name: job-agent) -> Attach policy: AmazonBedrockFullAccess ->
   Create access key (choose "Application running outside AWS") -> save both key values.
4. In your GitHub repo:
   - Settings -> Secrets and variables -> Actions -> Secrets tab: add AWS_ACCESS_KEY_ID and
     AWS_SECRET_ACCESS_KEY (plus the Telegram two). ANTHROPIC_API_KEY not needed on this route.
   - Same page -> Variables tab: add PROVIDER = bedrock, AWS_REGION = us-east-1,
     BEDROCK_MODEL_ID = (the inference profile ID from step 2).
5. Verify your credits cover Bedrock: AWS Billing -> Credits -> check "Amazon Bedrock" is listed
   under applicable services and note the expiry date.
To switch back to the direct Anthropic API later: set PROVIDER = anthropic and add ANTHROPIC_API_KEY.
