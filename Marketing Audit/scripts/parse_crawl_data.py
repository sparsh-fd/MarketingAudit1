"""
parse_crawl_data.py — Normalize raw Apify crawler outputs into consistent structures.

This module is imported by the marketing-audit skill to transform raw scraper
data into the standardized format expected by generate_report.py.

All functions handle missing/None data gracefully and return sensible defaults.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce a value to int, returning default on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    """Coerce a value to string, returning default if None."""
    if value is None:
        return default
    return str(value).strip()


def _parse_date(value: Any) -> Optional[str]:
    """Try to parse a date string into ISO format. Returns None on failure."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(value)[:10]


def _engagement_rate(likes: int, comments: int, followers: int) -> float:
    """Calculate engagement rate as a percentage."""
    if followers <= 0:
        return 0.0
    return round(((likes + comments) / followers) * 100, 2)


def _posts_per_week(dates: list[Optional[str]], lookback_days: int = 90) -> float:
    """Estimate posting frequency from a list of date strings."""
    valid_dates = []
    now = datetime.now()
    for d in dates:
        if not d:
            continue
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
            if (now - dt).days <= lookback_days:
                valid_dates.append(dt)
        except (ValueError, TypeError):
            continue

    if len(valid_dates) < 2:
        return round(len(valid_dates) / max(lookback_days / 7, 1), 2)

    span_days = (max(valid_dates) - min(valid_dates)).days
    if span_days <= 0:
        return 0.0
    weeks = span_days / 7
    return round(len(valid_dates) / weeks, 2)


# ---------------------------------------------------------------------------
# 1. Website crawl parser
# ---------------------------------------------------------------------------

def parse_website_crawl(raw_data: list[dict]) -> dict:
    """
    Parse raw output from apify/website-content-crawler.

    Args:
        raw_data: List of page objects from the crawler.

    Returns:
        Normalized website data with homepage content, blog stats,
        CTAs, meta tags, social links, trust signals, and email signup detection.
    """
    if not raw_data:
        return {
            "pages_crawled": 0,
            "homepage_content": "",
            "blog_posts": {"count": 0, "latest_date": None},
            "ctas_found": [],
            "meta_tags": [],
            "social_links": [],
            "trust_signals": [],
            "email_signup_found": False,
        }

    pages_crawled = len(raw_data)
    homepage_content = ""
    blog_posts: list[dict] = []
    ctas_found: list[str] = []
    meta_tags: list[dict] = []
    social_links: set[str] = set()
    trust_signals: list[str] = []
    email_signup_found = False

    social_domains = ("instagram.com", "facebook.com", "twitter.com", "x.com",
                      "linkedin.com", "tiktok.com", "youtube.com")
    cta_patterns = re.compile(
        r"(sign up|get started|book now|contact us|free trial|subscribe|"
        r"request demo|schedule|buy now|learn more|start free|join now)",
        re.IGNORECASE,
    )
    trust_patterns = re.compile(
        r"(testimonial|review|certified|partner|award|trust|guarantee|"
        r"as seen|featured in|accredited)",
        re.IGNORECASE,
    )
    email_patterns = re.compile(
        r"(newsletter|subscribe|email.*sign|opt.?in|lead.?magnet|download.*guide)",
        re.IGNORECASE,
    )

    for page in raw_data:
        url = _safe_str(page.get("url", ""))
        text = _safe_str(page.get("text", page.get("content", "")))
        title = _safe_str(page.get("title", ""))
        meta_desc = _safe_str(page.get("metaDescription", page.get("description", "")))

        # Homepage detection
        path = url.rstrip("/").split("/")[-1] if url else ""
        is_homepage = (not path or path in ("index", "home") or url.count("/") <= 3)
        if is_homepage and not homepage_content:
            homepage_content = text[:3000]

        # Blog post detection
        if any(seg in url.lower() for seg in ("/blog", "/news", "/article", "/post", "/resource")):
            pub_date = _parse_date(page.get("publishedDate", page.get("date")))
            blog_posts.append({"url": url, "title": title, "date": pub_date})

        # Meta tags
        if title or meta_desc:
            meta_tags.append({"url": url, "title": title, "description": meta_desc})

        # Social links from page content or extracted links
        links = page.get("links", page.get("urls", []))
        if isinstance(links, list):
            for link in links:
                link_url = link if isinstance(link, str) else _safe_str(link.get("href", ""))
                if any(domain in link_url.lower() for domain in social_domains):
                    social_links.add(link_url)

        # CTAs
        for match in cta_patterns.finditer(text[:2000]):
            cta = match.group(0).strip()
            if cta not in ctas_found:
                ctas_found.append(cta)

        # Trust signals
        if trust_patterns.search(text[:3000]):
            for match in trust_patterns.finditer(text[:3000]):
                signal = match.group(0).strip()
                if signal.lower() not in [t.lower() for t in trust_signals]:
                    trust_signals.append(signal)

        # Email signup
        if email_patterns.search(text[:2000]):
            email_signup_found = True

    # Sort blog posts by date descending
    blog_posts.sort(key=lambda x: x.get("date") or "0000-00-00", reverse=True)
    latest_blog_date = blog_posts[0]["date"] if blog_posts else None

    return {
        "pages_crawled": pages_crawled,
        "homepage_content": homepage_content,
        "blog_posts": {"count": len(blog_posts), "latest_date": latest_blog_date},
        "ctas_found": ctas_found[:10],
        "meta_tags": meta_tags[:10],
        "social_links": sorted(social_links),
        "trust_signals": trust_signals[:10],
        "email_signup_found": email_signup_found,
    }


# ---------------------------------------------------------------------------
# 2. Instagram parser
# ---------------------------------------------------------------------------

def parse_instagram_data(raw_data: list[dict]) -> dict:
    """
    Parse raw output from apify/instagram-scraper.

    Args:
        raw_data: List of post/profile objects from the scraper.

    Returns:
        Normalized Instagram metrics including engagement rate and posting frequency.
    """
    if not raw_data:
        return {
            "followers": 0,
            "following": 0,
            "posts_count": 0,
            "recent_posts": [],
            "avg_engagement_rate": 0.0,
            "posting_frequency_per_week": 0.0,
            "bio": "",
            "profile_complete": False,
        }

    # The first item may be profile data, or it may all be posts
    profile = {}
    posts = []

    for item in raw_data:
        if "followersCount" in item or "followers" in item:
            profile = item
        if "likesCount" in item or "likes" in item or "timestamp" in item:
            posts.append(item)

    # If no separate profile object, try to extract from first item
    if not profile and raw_data:
        profile = raw_data[0]

    followers = _safe_int(profile.get("followersCount", profile.get("followers")))
    following = _safe_int(profile.get("followingCount", profile.get("following")))
    posts_count = _safe_int(profile.get("postsCount", profile.get("posts_count", len(posts))))
    bio = _safe_str(profile.get("biography", profile.get("bio")))

    profile_complete = bool(
        bio
        and profile.get("profilePicUrl", profile.get("profilePic"))
        and profile.get("externalUrl", profile.get("website"))
    )

    # Parse recent posts
    recent_posts = []
    engagement_rates = []

    for post in posts[:12]:
        likes = _safe_int(post.get("likesCount", post.get("likes")))
        comments = _safe_int(post.get("commentsCount", post.get("comments")))
        post_date = _parse_date(post.get("timestamp", post.get("date", post.get("taken_at"))))
        post_type = _safe_str(post.get("type", post.get("mediaType", "image")))

        recent_posts.append({
            "date": post_date,
            "likes": likes,
            "comments": comments,
            "type": post_type,
        })

        if followers > 0:
            engagement_rates.append(_engagement_rate(likes, comments, followers))

    avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0.0
    post_dates = [p["date"] for p in recent_posts]
    freq = _posts_per_week(post_dates)

    return {
        "followers": followers,
        "following": following,
        "posts_count": posts_count,
        "recent_posts": recent_posts[:10],
        "avg_engagement_rate": avg_engagement,
        "posting_frequency_per_week": freq,
        "bio": bio,
        "profile_complete": profile_complete,
    }


# ---------------------------------------------------------------------------
# 3. Facebook parser
# ---------------------------------------------------------------------------

def parse_facebook_data(raw_data: list[dict]) -> dict:
    """
    Parse raw output from apify/facebook-posts-scraper.

    Args:
        raw_data: List of post/page objects from the scraper.

    Returns:
        Normalized Facebook page metrics.
    """
    if not raw_data:
        return {
            "page_likes": 0,
            "followers": 0,
            "posts_count": 0,
            "recent_posts": [],
            "avg_engagement_rate": 0.0,
            "posting_frequency_per_week": 0.0,
            "page_name": "",
            "profile_complete": False,
        }

    # Attempt to find page-level data
    page_info = {}
    posts = []

    for item in raw_data:
        if "likes" in item and "text" in item:
            posts.append(item)
        elif "pageLikes" in item or "likesCount" in item:
            page_info = item
        else:
            posts.append(item)

    if not page_info and raw_data:
        page_info = raw_data[0]

    page_likes = _safe_int(page_info.get("pageLikes", page_info.get("likes", page_info.get("likesCount"))))
    followers = _safe_int(page_info.get("followers", page_info.get("followersCount", page_likes)))
    page_name = _safe_str(page_info.get("pageName", page_info.get("name")))

    profile_complete = bool(
        page_name
        and page_info.get("about", page_info.get("description"))
        and page_info.get("profilePic", page_info.get("profileImage"))
    )

    recent_posts = []
    engagement_rates = []

    for post in posts[:10]:
        likes = _safe_int(post.get("likes", post.get("likesCount", post.get("reactions"))))
        comments = _safe_int(post.get("comments", post.get("commentsCount")))
        shares = _safe_int(post.get("shares", post.get("sharesCount")))
        post_date = _parse_date(post.get("time", post.get("date", post.get("timestamp"))))
        post_type = _safe_str(post.get("type", "post"))

        recent_posts.append({
            "date": post_date,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "type": post_type,
        })

        if followers > 0:
            engagement_rates.append(_engagement_rate(likes + shares, comments, followers))

    avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0.0
    post_dates = [p["date"] for p in recent_posts]
    freq = _posts_per_week(post_dates)

    return {
        "page_likes": page_likes,
        "followers": followers,
        "posts_count": len(posts),
        "recent_posts": recent_posts,
        "avg_engagement_rate": avg_engagement,
        "posting_frequency_per_week": freq,
        "page_name": page_name,
        "profile_complete": profile_complete,
    }


# ---------------------------------------------------------------------------
# 4. Twitter/X parser
# ---------------------------------------------------------------------------

def parse_twitter_data(raw_data: list[dict]) -> dict:
    """
    Parse raw output from apify/twitter-scraper.

    Args:
        raw_data: List of tweet/profile objects from the scraper.

    Returns:
        Normalized Twitter/X metrics.
    """
    if not raw_data:
        return {
            "followers": 0,
            "following": 0,
            "tweets_count": 0,
            "recent_tweets": [],
            "avg_engagement_rate": 0.0,
            "posting_frequency_per_week": 0.0,
            "bio": "",
            "profile_complete": False,
        }

    profile = {}
    tweets = []

    for item in raw_data:
        if "followersCount" in item or "followers_count" in item:
            profile = item
        if "retweetCount" in item or "retweet_count" in item or "text" in item:
            tweets.append(item)

    if not profile and raw_data:
        profile = raw_data[0]

    followers = _safe_int(profile.get("followersCount", profile.get("followers_count", profile.get("followers"))))
    following = _safe_int(profile.get("followingCount", profile.get("following_count", profile.get("following"))))
    tweets_count = _safe_int(profile.get("tweetsCount", profile.get("statuses_count", len(tweets))))
    bio = _safe_str(profile.get("description", profile.get("bio")))

    profile_complete = bool(
        bio
        and profile.get("profileImageUrl", profile.get("profile_image_url"))
        and profile.get("url", profile.get("website"))
    )

    recent_tweets = []
    engagement_rates = []

    for tweet in tweets[:15]:
        likes = _safe_int(tweet.get("likeCount", tweet.get("favorite_count", tweet.get("likes"))))
        retweets = _safe_int(tweet.get("retweetCount", tweet.get("retweet_count", tweet.get("retweets"))))
        replies = _safe_int(tweet.get("replyCount", tweet.get("reply_count", tweet.get("replies"))))
        tweet_date = _parse_date(tweet.get("createdAt", tweet.get("created_at", tweet.get("date"))))

        recent_tweets.append({
            "date": tweet_date,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
        })

        if followers > 0:
            total_engagement = likes + retweets + replies
            engagement_rates.append(round((total_engagement / followers) * 100, 2))

    avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0.0
    tweet_dates = [t["date"] for t in recent_tweets]
    freq = _posts_per_week(tweet_dates)

    return {
        "followers": followers,
        "following": following,
        "tweets_count": tweets_count,
        "recent_tweets": recent_tweets[:10],
        "avg_engagement_rate": avg_engagement,
        "posting_frequency_per_week": freq,
        "bio": bio,
        "profile_complete": profile_complete,
    }


# ---------------------------------------------------------------------------
# 5. SERP data parser
# ---------------------------------------------------------------------------

def parse_serp_data(raw_data: list[dict], business_name: str) -> dict:
    """
    Parse raw output from Google Search scraper.

    Args:
        raw_data: List of search result objects.
        business_name: The business name to search for in results.

    Returns:
        SERP analysis including position, Google Business presence, and reviews.
    """
    if not raw_data:
        return {
            "business_found_in_top_10": False,
            "position": None,
            "has_google_business": False,
            "review_count": 0,
            "avg_rating": 0.0,
            "competitors_in_results": [],
        }

    business_lower = business_name.lower()
    business_found = False
    position = None
    has_google_business = False
    review_count = 0
    avg_rating = 0.0
    competitors: list[str] = []

    for idx, result in enumerate(raw_data[:20], 1):
        title = _safe_str(result.get("title", "")).lower()
        url = _safe_str(result.get("url", result.get("link", ""))).lower()
        description = _safe_str(result.get("description", result.get("snippet", ""))).lower()

        # Check if this result belongs to the business
        name_match = (
            business_lower in title
            or business_lower.replace(" ", "") in url
            or business_lower in description[:100]
        )

        if name_match and not business_found and idx <= 10:
            business_found = True
            position = idx

        # Google Business Profile detection
        result_type = _safe_str(result.get("type", result.get("searchType", "")))
        if "local" in result_type.lower() or "maps" in url:
            if name_match:
                has_google_business = True

        # Knowledge panel / review data
        if name_match:
            review_count = _safe_int(result.get("reviewCount", result.get("reviews")))
            avg_rating = float(result.get("rating", result.get("stars", 0)) or 0)

        # Collect competitors (non-business results in top 10)
        if not name_match and idx <= 10:
            comp_title = _safe_str(result.get("title", ""))
            if comp_title and "..." not in comp_title[-4:]:
                competitors.append(comp_title)

    return {
        "business_found_in_top_10": business_found,
        "position": position,
        "has_google_business": has_google_business,
        "review_count": review_count,
        "avg_rating": avg_rating,
        "competitors_in_results": competitors[:5],
    }


# ---------------------------------------------------------------------------
# 6. Compile final audit JSON
# ---------------------------------------------------------------------------

def compile_audit_json(
    business_name: str,
    website_url: str,
    audit_date: str,
    overall_health: str,
    executive_summary: dict,
    channel_scores: list[dict],
    narrative_analysis: list[dict],
    gap_analysis: list[dict],
    competitor_swot: list[dict],
    recommendations: list[dict],
) -> dict:
    """
    Combine all parsed data into the JSON structure expected by generate_report.py.

    Args:
        business_name: Name of the audited business.
        website_url: Primary website URL.
        audit_date: Date of the audit (ISO format string).
        overall_health: One of Strong, Moderate, Weak, Critical.
        executive_summary: Dict with overview, top_strengths, top_gaps.
        channel_scores: List of {channel, score, evidence} dicts.
        narrative_analysis: List of {channel, content} dicts.
        gap_analysis: List of {channel, current_state, best_practice, impact} dicts.
        competitor_swot: List of competitor SWOT dicts.
        recommendations: List of {channel, action, impact, effort} dicts.

    Returns:
        Complete audit data dict matching the generate_report.py input schema.
    """
    # Validate and default executive_summary
    es = executive_summary or {}
    es.setdefault("overview", "")
    es.setdefault("top_strengths", [])
    es.setdefault("top_gaps", [])

    # Validate channel_scores
    valid_scores = {"Strong", "Moderate", "Weak", "Critical"}
    for item in (channel_scores or []):
        if item.get("score") not in valid_scores:
            item["score"] = "Weak"

    # Validate overall_health
    if overall_health not in valid_scores:
        overall_health = "Moderate"

    # Validate recommendations effort levels
    valid_efforts = {"Quick Win", "Medium Lift", "Strategic"}
    for rec in (recommendations or []):
        if rec.get("effort") not in valid_efforts:
            rec["effort"] = "Medium Lift"

    return {
        "business_name": _safe_str(business_name, "Unknown Business"),
        "website_url": _safe_str(website_url),
        "audit_date": _safe_str(audit_date, datetime.now().strftime("%Y-%m-%d")),
        "overall_health": overall_health,
        "executive_summary": es,
        "channel_scores": channel_scores or [],
        "narrative_analysis": narrative_analysis or [],
        "gap_analysis": gap_analysis or [],
        "competitor_swot": competitor_swot or [],
        "recommendations": recommendations or [],
    }
