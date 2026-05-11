"""
GoToRetreats Marketing Audit — Backend API

Single endpoint: POST /api/audit
Accepts: { business_name, website_url, email }
Returns: PDF file download

Flow: collect lead → crawl site → Claude API analysis → generate PDF → return file
"""

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_SCRIPT_URL = os.environ.get("GOOGLE_SCRIPT_URL", "")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr

from pdf_generator import build_pdf

app = FastAPI(title="GoToRetreats Marketing Audit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    business_name: str
    website_url: str
    email: str


def normalize_url(raw: str) -> str:
    u = raw.strip()
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    return u


async def log_to_google_sheet(data: dict):
    if not GOOGLE_SCRIPT_URL:
        return
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            await client.post(GOOGLE_SCRIPT_URL, json=data, timeout=10)
    except Exception:
        pass


EMPTY_CRAWL = {
    "body_text": "",
    "pages_crawled": 0,
    "has_ssl": False,
    "title": "",
    "meta_description": "",
    "social_links": [],
    "has_blog": False,
    "has_email_signup": False,
    "has_testimonials": False,
    "has_booking": False,
    "has_pricing": False,
    "has_faq": False,
    "has_video": False,
}


async def crawl_website(url: str) -> dict:
    if not APIFY_API_TOKEN:
        return {"url": url, **EMPTY_CRAWL}
    try:
        from apify_client import ApifyClient
        client = ApifyClient(APIFY_API_TOKEN)
        run_input = {
            "startUrls": [{"url": url}],
            "maxCrawlPages": 15,
            "crawlerType": "cheerio",
        }
        run = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: client.actor("apify/website-content-crawler").call(run_input=run_input)
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        combined_text = " ".join(
            item.get("text", "") or item.get("markdown", "")
            for item in items
        )[:8000]
        first = items[0] if items else {}
        return {
            "url": url,
            "body_text": combined_text,
            "pages_crawled": len(items),
            "has_ssl": url.startswith("https"),
            "title": first.get("title", ""),
            "meta_description": first.get("metadata", {}).get("description", ""),
            "social_links": [],
            "has_blog": "blog" in combined_text.lower(),
            "has_email_signup": "subscribe" in combined_text.lower() or "newsletter" in combined_text.lower(),
            "has_testimonials": "testimonial" in combined_text.lower() or "review" in combined_text.lower(),
            "has_booking": "book" in combined_text.lower() or "reserve" in combined_text.lower(),
            "has_pricing": "price" in combined_text.lower() or "from $" in combined_text.lower(),
            "has_faq": "faq" in combined_text.lower(),
            "has_video": "video" in combined_text.lower() or "youtube" in combined_text.lower(),
        }
    except Exception as e:
        print(f"Apify crawl failed: {e}, returning empty crawl")
        return {"url": url, **EMPTY_CRAWL}


AUDIT_SYSTEM_PROMPT = """You are a retreat and wellness marketing audit expert working for GoToRetreats.
You will receive crawled website data for a retreat business. Analyze it across 12 specific categories
and return ONLY a valid JSON object (no markdown, no code fences, no explanation).

The 12 audit categories are:
1. SEO & AI Discoverability
2. Homepage Messaging
3. Retreat Positioning
4. Trust & Social Proof
5. Booking Funnel Experience
6. Mobile Optimization
7. Speed & Performance
8. Branding Consistency
9. Conversion Opportunities
10. Content & Storytelling
11. Email Capture Strategy
12. Google & AI Search Readiness

Return this exact JSON structure:
{
  "business_name": "string",
  "website_url": "string",
  "audit_date": "YYYY-MM-DD",
  "industry": "string",
  "overall_health": "Strong|Moderate|Weak|Critical",
  "executive_summary": {
    "overview": "3-5 sentence summary of overall marketing health",
    "top_strengths": ["strength1", "strength2", "strength3"],
    "top_gaps": ["gap1", "gap2", "gap3"]
  },
  "channel_scores": [
    {"channel": "SEO & AI Discoverability", "score": "Strong|Moderate|Weak|Critical", "evidence": "1-line evidence"},
    {"channel": "Homepage Messaging", "score": "...", "evidence": "..."},
    {"channel": "Retreat Positioning", "score": "...", "evidence": "..."},
    {"channel": "Trust & Social Proof", "score": "...", "evidence": "..."},
    {"channel": "Booking Funnel Experience", "score": "...", "evidence": "..."},
    {"channel": "Mobile Optimization", "score": "...", "evidence": "..."},
    {"channel": "Speed & Performance", "score": "...", "evidence": "..."},
    {"channel": "Branding Consistency", "score": "...", "evidence": "..."},
    {"channel": "Conversion Opportunities", "score": "...", "evidence": "..."},
    {"channel": "Content & Storytelling", "score": "...", "evidence": "..."},
    {"channel": "Email Capture Strategy", "score": "...", "evidence": "..."},
    {"channel": "Google & AI Search Readiness", "score": "...", "evidence": "..."}
  ],
  "narrative_analysis": [
    {"channel": "Category Name", "content": "2-4 paragraph detailed analysis with specific evidence from the crawl data"}
  ],
  "gap_analysis": [
    {"channel": "Category Name", "current_state": "what exists now", "best_practice": "what should exist", "impact": "High|Medium|Low"}
  ],
  "competitor_swot": [
    {"competitor_name": "...", "website": "...", "positioning": "...", "strengths": ["..."], "weaknesses": ["..."], "opportunities": ["..."], "threats": ["..."]}
  ],
  "recommendations": [
    {"channel": "Category Name", "action": "specific actionable recommendation", "impact": "High|Medium|Low", "effort": "Quick Win|Medium Effort|Strategic"}
  ]
}

Scoring rubric:
- SEO: unique meta titles/descriptions per page, schema markup, Google Business Profile, XML sitemap
- Homepage Messaging: clear headline, specific value prop, emotional hook, CTA above fold
- Retreat Positioning: clear niche, transformation promise, ideal guest defined, pricing visible
- Trust & Social Proof: 10+ testimonials=Strong, 3-9=Moderate, <3=Weak; external reviews
- Booking Funnel: CTA on every page, 3 or fewer steps, multiple payment options, live availability
- Mobile: fully responsive, touch targets >44px, LCP <2.5s
- Speed: LCP <2.5s=Strong, 2.5-4s=Moderate, >4s=Weak; optimized images; CDN
- Branding: consistent visual identity, tone, photography across all channels
- Conversion: 2-3 CTAs per page, lead magnets, urgency triggers, retargeting pixels
- Content: 4+ posts/month=Strong, 1-3=Moderate, <1=Weak; video; guest stories
- Email Capture: visible signup, lead magnet, welcome sequence, segmentation
- AI Search: FAQ schema, conversational content, featured snippet eligible, voice search ready

Overall: Strong=8+ Strong no Critical, Moderate=5-7 Strong max 1 Critical, Weak=<5 Strong or 3+ Weak/Critical, Critical=6+ Weak/Critical

Include minimum 15 gaps and 12-18 recommendations. Every finding must cite evidence from the crawl data.
Return ONLY the JSON."""


def _build_user_prompt(business_name: str, url: str, crawl_data: dict) -> str:
    crawl_summary = json.dumps(crawl_data, indent=2, default=str)[:12000]
    return f"""Run a full marketing audit for this retreat/wellness business:

Business: {business_name}
Website: {url}

Here is the crawled website data:
{crawl_summary}

Analyze across all 12 categories. Base your findings on the actual crawl data provided.
Return the complete audit JSON."""


def _extract_json(text: str) -> dict:
    from json_repair import repair_json
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise ValueError("AI response did not contain valid JSON")
    repaired = repair_json(json_match.group(0))
    return json.loads(repaired)


async def _run_claude_audit(user_prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        system=AUDIT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    text = message.content[0].text
    return _extract_json(text)


async def _run_openai_audit(user_prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            },
            json={
                "model": "gpt-4o",
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )

    if resp.status_code != 200:
        err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg = err.get("error", {}).get("message", f"OpenAI API error: {resp.status_code}")
        raise RuntimeError(msg)

    result = resp.json()
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _extract_json(text)


async def run_audit(business_name: str, url: str, crawl_data: dict) -> dict:
    user_prompt = _build_user_prompt(business_name, url, crawl_data)
    providers = []
    if ANTHROPIC_API_KEY:
        providers.append(("Claude", _run_claude_audit))
    if OPENAI_API_KEY:
        providers.append(("OpenAI", _run_openai_audit))

    if not providers:
        raise HTTPException(status_code=500, detail="No AI API keys configured.")

    last_error = None
    for name, fn in providers:
        try:
            print(f"Trying {name} for audit...")
            return await fn(user_prompt)
        except Exception as e:
            print(f"{name} failed: {e}")
            last_error = e

    raise HTTPException(status_code=502, detail=f"All AI providers failed. Last error: {last_error}")


@app.post("/api/audit")
async def create_audit(req: AuditRequest):
    url = normalize_url(req.website_url)
    now = datetime.now(timezone.utc).isoformat()

    await log_to_google_sheet({
        "business_name": req.business_name,
        "website_url": url,
        "email": req.email,
        "submitted_at": now,
    })

    crawl_data = await crawl_website(url)
    audit_data = await run_audit(req.business_name, url, crawl_data)

    audit_data.setdefault("business_name", req.business_name)
    audit_data.setdefault("website_url", url)
    audit_data.setdefault("audit_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    slug = re.sub(r"[^a-z0-9]+", "_", req.business_name.lower().strip()).strip("_")
    tmp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp_dir, f"marketing_audit_{slug}.pdf")

    json_path = os.path.join(tmp_dir, "audit_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    build_pdf(audit_data, pdf_path)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"marketing_audit_{slug}.pdf",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GoToRetreats Marketing Audit API"}
