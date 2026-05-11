# Marketing Audit — Project Notes

## Infrastructure

- **Web & social crawling**: Uses the [Apify MCP server](https://apify.com/mcp) for all web and social media data collection.
- **Marketing audit skill**: Lives at `~/.claude/skills/marketing-audit/`.
- **PDF generation**: Python scripts use `reportlab` for all PDF output.

## Audit Structure

The audit covers **12 retreat-focused categories** (not the old 6 generic channels):

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

Scoring rubrics live in `references/channel-benchmarks.md`. Each category scored as Strong / Moderate / Weak / Critical.

## Branding

All audit PDFs **must** use GoToRetreats branding loaded from:

```
~/.claude/skills/marketing-audit/assets/brand-config.json
```

Never use generic or client-specific branding — every report is produced under the GoToRetreats brand identity.
