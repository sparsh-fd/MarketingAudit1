"""
GoToRetreats Marketing Audit — Backend API

Single endpoint: POST /api/audit
Accepts: { business_name, website_url, email }
Returns: PDF file download

Flow: collect lead → crawl site → Claude API analysis → generate PDF → return file
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

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


async def crawl_website(url: str) -> dict:
    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "headings": [],
        "cta_texts": [],
        "has_ssl": url.startswith("https"),
        "social_links": [],
        "has_blog": False,
        "has_email_signup": False,
        "has_testimonials": False,
        "has_booking": False,
        "has_pricing": False,
        "has_faq": False,
        "has_video": False,
        "images_count": 0,
        "scripts_count": 0,
        "body_text": "",
        "nav_items": [],
        "page_links": [],
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers={"User-Agent": "GoToRetreats-Audit-Bot/1.0"})
            html = resp.text
    except Exception as e:
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        result["meta_description"] = meta_desc.get("content", "")

    for level in ["h1", "h2", "h3"]:
        for tag in soup.find_all(level, limit=10):
            result["headings"].append({"level": level, "text": tag.get_text(strip=True)})

    for a in soup.find_all("a", limit=100):
        href = (a.get("href") or "").lower()
        text = a.get_text(strip=True).lower()

        for platform in ["instagram", "facebook", "twitter", "linkedin", "tiktok", "youtube"]:
            if platform in href:
                result["social_links"].append({"platform": platform, "url": a.get("href")})

        if any(w in text for w in ["book", "reserve", "sign up", "get started", "join", "apply"]):
            result["cta_texts"].append(a.get_text(strip=True))

        if any(w in href for w in ["/blog", "/articles", "/resources", "/journal", "/news"]):
            result["has_blog"] = True

        result["page_links"].append({"text": a.get_text(strip=True)[:60], "href": href[:200]})

    nav = soup.find("nav")
    if nav:
        for li in nav.find_all(["a", "li"], limit=15):
            t = li.get_text(strip=True)
            if t and len(t) < 40:
                result["nav_items"].append(t)

    body_text = soup.get_text(separator=" ", strip=True).lower()
    result["body_text"] = body_text[:5000]

    result["has_email_signup"] = bool(
        soup.find("input", {"type": "email"})
        or "newsletter" in body_text
        or "subscribe" in body_text
    )
    result["has_testimonials"] = any(
        w in body_text for w in ["testimonial", "review", "what our", "guest stories", "★", "⭐"]
    )
    result["has_booking"] = any(
        w in body_text for w in ["book now", "reserve", "booking", "check availability", "schedule"]
    )
    result["has_pricing"] = any(
        w in body_text for w in ["pricing", "price", "from $", "per person", "per night", "starts at"]
    )
    result["has_faq"] = any(
        w in body_text for w in ["faq", "frequently asked", "common questions"]
    )
    result["has_video"] = bool(
        soup.find("video") or soup.find("iframe", src=re.compile(r"youtube|vimeo", re.I))
    )
    result["images_count"] = len(soup.find_all("img"))
    result["scripts_count"] = len(soup.find_all("script"))

    for meta in soup.find_all("meta"):
        if meta.get("property", "").startswith("og:") or meta.get("name") in ["robots", "viewport"]:
            pass

    schema_scripts = soup.find_all("script", {"type": "application/ld+json"})
    result["has_schema"] = len(schema_scripts) > 0
    result["schema_types"] = []
    for s in schema_scripts:
        try:
            sd = json.loads(s.string)
            if isinstance(sd, dict) and "@type" in sd:
                result["schema_types"].append(sd["@type"])
        except Exception:
            pass

    return result


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
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise ValueError("AI response did not contain valid JSON")
    return json.loads(json_match.group(0))


async def _run_claude_audit(user_prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "system": AUDIT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )

    if resp.status_code != 200:
        err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg = err.get("error", {}).get("message", f"Claude API error: {resp.status_code}")
        raise RuntimeError(msg)

    result = resp.json()
    text = result.get("content", [{}])[0].get("text", "")
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
        raise HTTPException(status_code=500, detail="No AI API keys configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

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

    # 1. Log to Google Sheet (fire and forget)
    await log_to_google_sheet({
        "business_name": req.business_name,
        "website_url": url,
        "email": req.email,
        "submitted_at": now,
    })

    # 2. Crawl the website
    crawl_data = await crawl_website(url)

    # 3. Run AI audit (tries Claude first, falls back to OpenAI)
    audit_data = await run_audit(req.business_name, url, crawl_data)

    # Ensure required fields
    audit_data.setdefault("business_name", req.business_name)
    audit_data.setdefault("website_url", url)
    audit_data.setdefault("audit_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # 4. Generate PDF
    slug = re.sub(r"[^a-z0-9]+", "_", req.business_name.lower().strip()).strip("_")
    tmp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp_dir, f"marketing_audit_{slug}.pdf")

    json_path = os.path.join(tmp_dir, "audit_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    build_pdf(audit_data, pdf_path)

    # 5. Return PDF
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"marketing_audit_{slug}.pdf",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GoToRetreats Marketing Audit API"}
