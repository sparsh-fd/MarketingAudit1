---
name: marketing-audit
description: >
  Perform a comprehensive marketing audit for any retreat or wellness business. Use this skill
  whenever the user asks to audit, review, analyze, assess, or evaluate a business's marketing,
  even casually like "check our marketing", "audit my brand", or "how's our marketing doing".
  Also triggers on: business name + URL, brand health check, competitor analysis, or any request
  to grade/score marketing performance. Covers 12 retreat-focused categories. Delivers a branded
  GoToRetreats PDF report.
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - WebFetch
  - WebSearch
  - "mcp__apify__*"
  - "mcp__Claude_in_Chrome__*"
---

# Marketing Audit Skill

Run a full marketing audit for any retreat or wellness business and deliver a branded
GoToRetreats PDF report covering 12 categories.

Work through Steps 1–9 in order. Do NOT skip steps. If a data source fails, follow the fallback
in that step and continue — never stop the audit because one crawl failed.

---

## Step 1: Gather Inputs

**Required**: business name, website URL.

If the user provides only a URL, extract the business name from the website after crawling.
Only ask the user for information that cannot be discovered through crawling or search.

**Auto-discover** (do not ask the user):
- Social media profile URLs
- Retreat type / niche (yoga, wellness, meditation, etc.)
- Target audience
- Top 2–3 competitors

**Optional** (ask only if relevant):
- Specific marketing goals
- Approximate marketing budget range

Once you have at minimum the business name and URL, proceed immediately.

---

## Step 2: Website Crawling

Use the Apify `website-content-crawler` actor to crawl the business website. Set max pages to 20.

Extract and note the following:
- Homepage content: headline, value proposition, primary CTAs, hero image/video
- Retreat listing pages: pricing, dates, availability, descriptions
- Blog / resource section: count of posts, publication date of the 3 most recent
- Navigation structure: main menu items, depth, clarity
- Trust signals: guest reviews/testimonials, certifications, partner logos, press mentions
- Email capture: newsletter signup forms, lead magnets, popup opt-ins
- SEO metadata: meta titles and descriptions from homepage, about page, and retreat pages
- Social links: any social media URLs found in header, footer, or sidebar
- Booking flow: how many steps from landing to payment, payment options
- Mobile layout: viewport meta tag, responsive design indicators
- Page speed indicators: image sizes, script count, load time

**Fallback chain** (try each in order until one works):

1. **Apify crawler fails** → Try `WebFetch` on the homepage URL. If it returns only a title tag
   or meta content (common with JavaScript SPAs), proceed to step 2.
2. **WebFetch returns minimal content** → Use browser automation tools (`mcp__Claude_in_Chrome__*`)
   to navigate to the site, take a screenshot, and use `read_page` to extract the rendered DOM.
   This handles React/Vue/Angular SPAs that require JavaScript execution.
3. **No browser tools available** → Use `WebSearch` for `site:[domain]` to find indexed pages,
   and `WebFetch` on any cached or indexed subpages.
4. **Site completely unreachable** → Mark relevant categories as **Critical** and note it.

**Important**: If WebFetch returns only a page title, this likely means the site is a JavaScript
SPA with no server-side rendering. This is itself a significant SEO finding — note it in the
SEO & AI Discoverability analysis.

---

## Step 3: Social Media Discovery & Crawling

### 3a: Discover profiles

1. Check the social links extracted from the website crawl (Step 2).
2. For any platforms not found, web search: `"[business name]" site:instagram.com`,
   `"[business name]" site:linkedin.com`, etc.
3. Check these platforms: **Instagram, Facebook, Twitter/X, LinkedIn, TikTok, YouTube**.

### 3b: Crawl each discovered platform

Use the appropriate Apify actor for each platform:

| Platform   | Actor                           | Key data points                                    |
|------------|----------------------------------|----------------------------------------------------|
| Instagram  | `apify/instagram-scraper`        | Follower count, recent 12 posts, engagement rate    |
| Facebook   | `apify/facebook-posts-scraper`   | Page likes, recent 10 posts, post engagement        |
| Twitter/X  | `apify/twitter-scraper`          | Follower count, recent 15 tweets, retweet/like avg  |
| LinkedIn   | Web search only                  | Company page presence, posting frequency estimate   |
| TikTok     | `clockworks/tiktok-scraper`      | Follower count, recent 10 videos, avg views         |
| YouTube    | Web search + channel page fetch  | Subscriber count, upload frequency, recent 5 videos |

For each platform, record:
- **Follower / subscriber count**
- **Posting frequency** (posts per week, estimated from last 10–15 posts)
- **Engagement signals** (likes, comments, shares relative to follower count)
- **Content types** (images, video, carousels, stories, reels, articles)
- **Brand consistency** (profile photo, bio, link-in-bio, tone alignment with website)

If a platform is not found, mark it as **absent** in the audit.

**Fallback**: If an Apify scraper fails for a platform, fall back to `WebSearch` + `WebFetch`
to gather whatever public data is available for that platform.

---

## Step 4: SEO & Search Visibility Research

Use the Apify `google-search-scraper` actor to run these searches:

1. The exact business name (quoted)
2. 3–5 key retreat-related search terms (e.g., "yoga retreat [location]", "wellness retreat near me")
3. `"[business name]" reviews`

From the results, assess:
- **SERP position**: Where does the business rank for its own name and key terms?
- **Meta descriptions**: Are they compelling and keyword-relevant in search results?
- **Google Business Profile**: Present? Claimed? Reviews count and average rating?
- **Knowledge panel**: Does one appear for the business name search?
- **Review presence**: Ratings on Google, TripAdvisor, Trustpilot, or retreat directories?
- **AI overview / SGE**: Is the business cited in AI-generated search responses?
- **Featured snippets**: Does the site appear in or qualify for featured snippets?

Additionally, check for:
- Schema markup (FAQ, Review, Event, Product) via source inspection
- Voice search readiness: does content match conversational queries?

---

## Step 5: Competitor Research

Identify 2–3 direct competitors using:
1. Competitors mentioned or compared on the business's own website
2. Web search: `top [retreat type] retreats [region]` or `retreats like [business name]`
3. Competitors appearing in SERP results for the business's key terms (Step 4)

If no competitors can be identified, use 2 well-known players in the same retreat niche as proxies.

For each competitor, gather:
- Website quality: design polish, messaging clarity, booking flow
- Social media: which platforms, follower counts, posting frequency
- Content strategy: blog presence, guest stories, video content
- Retreat positioning: niche, transformation promise, pricing transparency
- Trust signals: reviews, certifications, media mentions

Load `references/swot-prompts.md` and use the structured questions to build a SWOT analysis
(Strengths, Weaknesses, Opportunities, Threats) for the audited business relative to each competitor.

---

## Step 6: Score All Categories

Load `references/channel-benchmarks.md` for the scoring rubric and benchmark criteria.

Score each of these **12 categories** using the rubric:

| #  | Category                        | Possible Scores                          |
|----|---------------------------------|------------------------------------------|
| 1  | SEO & AI Discoverability        | Strong / Moderate / Weak / Critical      |
| 2  | Homepage Messaging              | Strong / Moderate / Weak / Critical      |
| 3  | Retreat Positioning             | Strong / Moderate / Weak / Critical      |
| 4  | Trust & Social Proof            | Strong / Moderate / Weak / Critical      |
| 5  | Booking Funnel Experience       | Strong / Moderate / Weak / Critical      |
| 6  | Mobile Optimization             | Strong / Moderate / Weak / Critical      |
| 7  | Speed & Performance             | Strong / Moderate / Weak / Critical      |
| 8  | Branding Consistency            | Strong / Moderate / Weak / Critical      |
| 9  | Conversion Opportunities        | Strong / Moderate / Weak / Critical      |
| 10 | Content & Storytelling          | Strong / Moderate / Weak / Critical      |
| 11 | Email Capture Strategy          | Strong / Moderate / Weak / Critical      |
| 12 | Google & AI Search Readiness    | Strong / Moderate / Weak / Critical      |

Each score MUST be backed by specific evidence from the research — never assign a score
without citing the data that supports it.

Derive an **Overall Marketing Health** label:
- **Strong**: 8+ categories Strong, no Critical
- **Moderate**: 5–7 categories Strong, at most 1 Critical
- **Weak**: Fewer than 5 Strong, or 3+ Weak/Critical
- **Critical**: 6+ categories Weak or Critical

---

## Step 7: Build the Report

Compile all findings into a structured JSON object with these sections:

### 7.1 Executive Summary
- 3–5 sentences summarizing overall marketing health
- The Overall Marketing Health label
- Top 3 strengths (specific, evidence-backed)
- Top 3 gaps (specific, evidence-backed)

### 7.2 Category Scores Table
- All 12 categories with their score label and a 1-line evidence summary

### 7.3 Narrative Analysis
- 2–4 paragraphs per category with specific evidence from the research
- Reference actual data: follower counts, post frequencies, SERP positions, page speeds, etc.
- Do NOT write generic marketing advice — every claim must cite researched evidence

### 7.4 Gap Analysis
- Table format: Category | Current State | Best Practice | Impact Rating (High/Medium/Low)
- Minimum 15 gaps across all categories
- Impact rating reflects business consequence, not just best-practice deviation

### 7.5 Competitor SWOT
- 2–3 competitors
- Each with all 4 quadrants: Strengths, Weaknesses, Opportunities, Threats
- Focus on positioning relative to the audited business

### 7.6 Recommendations
- 12–18 specific, actionable recommendations
- Group by category
- Each recommendation includes:
  - What to do (specific action, not "improve your SEO")
  - Why it matters (tied to a gap or competitor advantage)
  - Effort level: Quick Win / Medium Effort / Major Initiative

### JSON Schema

```json
{
  "business_name": "string",
  "website_url": "string",
  "audit_date": "YYYY-MM-DD",
  "industry": "string",
  "overall_health": "Strong|Moderate|Weak|Critical",
  "executive_summary": {
    "overview": "3-5 sentence summary",
    "top_strengths": ["strength1", "strength2", "strength3"],
    "top_gaps": ["gap1", "gap2", "gap3"]
  },
  "channel_scores": [
    {"channel": "SEO & AI Discoverability", "score": "Strong|Moderate|Weak|Critical", "evidence": "1-line"},
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
    {"channel": "Category Name", "content": "2-4 paragraph analysis with specific data"}
  ],
  "gap_analysis": [
    {"channel": "...", "current_state": "...", "best_practice": "...", "impact": "High|Medium|Low"}
  ],
  "competitor_swot": [
    {"competitor_name": "...", "website": "...", "positioning": "...", "strengths": [], "weaknesses": [], "opportunities": [], "threats": []}
  ],
  "recommendations": [
    {"channel": "...", "action": "specific action", "impact": "High|Medium|Low", "effort": "Quick Win|Medium Effort|Strategic"}
  ]
}
```

---

## Step 8: Generate the PDF

### 8a: Load branding

Read the brand config from `assets/brand-config.json` (relative to this skill directory).

**CRITICAL**: ALL PDFs use GoToRetreats branding. The report is produced BY GoToRetreats FOR
the client. Never use the audited business's logo, colors, or fonts.

### 8b: Write report data

Write the structured report data (from Step 7) as a JSON file to a temp location the
Python script can read.

### 8c: Run the PDF generator

```bash
python ~/.claude/skills/marketing-audit/scripts/generate_report.py \
  --data <path_to_report_json> \
  --brand ~/.claude/skills/marketing-audit/assets/brand-config.json \
  --output marketing_audit_<business_name_slug>.pdf
```

### 8d: PDF design specification

The Python script must produce a PDF with these exact design elements:

**Cover page**:
- GoToRetreats logo PNG centered
- Decorative horizontal divider — #00D1CE, centered
- "Marketing Intelligence Report" — centered, Helvetica-Bold 28pt, #4A4A4F
- Client business name — centered below, Helvetica 18pt, #4A4A4F
- Audit date — centered, Helvetica 14pt, #B8BFD1

**Page header** (every page after cover):
- GoToRetreats logo PNG — top-left
- "Marketing Intelligence Report" — top-right, #B8BFD1, Helvetica 10pt

**Page footer** (every page):
- Thin horizontal rule in #009E9B
- Page number centered, Helvetica 9pt, #B8BFD1

**Section headings**:
- #009E9B, Helvetica-Bold 14pt
- 3pt colored left-border accent in #00D1CE

**Body text**: Helvetica 10pt, #4A4A4F, 14pt leading

**Tables**:
- Header row: background #009E9B, text #FFFFFF, Helvetica-Bold 10pt
- Data rows: alternating #FAFAFA and #FFFFFF
- Cell padding: 6pt

**Score badges**: Inline colored labels —
- Strong: #16A34A background, white text
- Moderate: #D97706 background, white text
- Weak: #EA580C background, white text
- Critical: #DC2626 background, white text

**SWOT grids**: 2×2 table per competitor, quadrant headers in #00D1CE with white text

**Output filename**: `marketing_audit_<business_name_slug>.pdf`
where `<business_name_slug>` is the business name lowercased, spaces replaced with underscores,
special characters removed.

---

## Step 9: Present Results

After the PDF is generated, present it to the user with a brief summary in chat.

The chat summary should be exactly 3–4 lines:
1. Overall Marketing Health label and what it means
2. The single biggest strength
3. The most critical gap or opportunity
4. The PDF filename and location

Do NOT reproduce the full report in chat. The PDF is the deliverable.

---

## Error Handling

| Scenario                        | Action                                                        |
|---------------------------------|---------------------------------------------------------------|
| Website unreachable             | Mark relevant categories as **Critical**, proceed with web search |
| No social profiles found        | Mark Branding Consistency and Content as **Weak/Critical**    |
| Apify scraper fails             | Fall back to `WebSearch` + `WebFetch` for that data point     |
| No competitors found            | Use 2 well-known retreat industry players as proxies          |
| PDF generation script fails     | Print error, attempt to fix, retry once                       |
| Brand config missing            | Stop and alert user — branding is mandatory                   |

Never halt the entire audit because one data source failed. Degrade gracefully, note the gap
in the report, and continue.

---

## Quality Checklist

Before generating the PDF, self-verify every item:

- [ ] All 12 categories scored with specific evidence (no unscored categories)
- [ ] Narrative analysis uses researched data, not generic filler
- [ ] At least 15 gaps in the gap analysis table
- [ ] 2–3 competitors with all 4 SWOT quadrants populated
- [ ] Recommendations are specific and actionable (not "improve your SEO")
- [ ] Each recommendation has an effort level assigned
- [ ] 12–18 total recommendations covering multiple categories
- [ ] Executive summary has overall health label, top 3 strengths, top 3 gaps
- [ ] PDF uses GoToRetreats branding from `assets/brand-config.json` — not the client's
- [ ] PDF renders with correct colors, fonts, headers, footers, and score badges
- [ ] Output filename follows the `marketing_audit_<slug>.pdf` convention
