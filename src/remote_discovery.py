"""Permitted public-feed connectors for India-eligible remote PM/Scrum roles.

This module does not scrape login-gated job boards. Each adapter preserves source
attribution and original apply URLs; verify source terms before production use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests

INDIA = "India"
ROLE_TERMS = (
    "project manager", "technical project manager", "it project manager",
    "software project manager", "digital project manager", "program manager",
    "technical program manager", "delivery manager", "scrum master",
    "senior scrum master", "agile project manager",
)
TIMEOUT = 25
HEADERS = {"User-Agent": "JobRadar/0.2 (personal job-search research)"}


def _text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value)))).strip()


def _date(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
        except Exception:
            return None


def _eligible_text(text):
    value = (text or "").lower()
    restricted = ("us only", "usa only", "united states only", "uk only",
                  "canada only", "europe only", "must be located in the us",
                  "must reside in the united states")
    if any(term in value for term in restricted):
        return "EXCLUDED", "Source text indicates a country restriction; manual review required"
    if "india" in value:
        return "CONFIRMED", "India explicitly appears in source location/eligibility text"
    if any(term in value for term in ("worldwide", "work from anywhere", "any location", "global remote")):
        return "CONFIRMED", "Worldwide/anywhere eligibility stated by source"
    if any(term in value for term in ("asia", "apac")):
        return "REVIEW", "Regional remote scope; India eligibility not guaranteed"
    return "REVIEW", "Remote listing does not establish India eligibility"


def _normalise(source, source_id, title, company, url, description, location,
               employment="", posted=None, salary="", attribution_url=None):
    eligibility, reason = _eligible_text(location or "")
    return {
        "source": source, "source_job_id": str(source_id or url),
        "title": _text(title), "company": _text(company) or "Not specified",
        "url": url or "", "description": _text(description),
        "location": _text(location), "employment_type": _text(employment),
        "posted_at": _date(posted), "eligibility_status": eligibility,
        "eligibility_reason": reason, "source_attribution": attribution_url or "",
    }


def _matches_role(job):
    title = job["title"].lower()
    return any(term in title for term in ROLE_TERMS)


def fetch_himalayas():
    results = []
    # Search each target title in India and worldwide feeds. Search results are
    # source data, not proof of eligibility; local eligibility checks still apply.
    for term in ROLE_TERMS:
        params = urlencode({"q": term, "country": "IN", "worldwide": "true", "sort": "recent"})
        url = "https://himalayas.app/jobs/api/search?" + params
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("jobs", []):
            guid = item.get("guid")
            apply_url = item.get("applicationLink") or ""
            loc = " ".join(item.get("locationRestrictions") or []) or "Not specified"
            job = _normalise("Himalayas", guid, item.get("title"), item.get("companyName"),
                apply_url, item.get("description") or item.get("excerpt"), loc,
                item.get("employmentType"), item.get("pubDate"),
                attribution_url="https://himalayas.app")
            job["source_job_id"] = str(guid or apply_url)
            job["source_attribution"] = "Himalayas — https://himalayas.app"
            if job["url"] and _matches_role(job):
                results.append(job)
    return results


def fetch_remoteok():
    response = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        tags = " ".join(item.get("tags") or [])
        loc = " ".join([item.get("location") or "", tags])
        job = _normalise("Remote OK", item.get("id"), item.get("position"),
            item.get("company"), item.get("url"), item.get("description"), loc,
            item.get("employment_type") or "", item.get("date"), attribution_url="https://remoteok.com")
        if job["url"] and _matches_role(job):
            results.append(job)
    return results


def fetch_wwr():
    response = requests.get("https://weworkremotely.com/remote-jobs.rss", headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    results = []
    for item in root.findall(".//item"):
        title = _text(item.findtext("title"))
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        pub = item.findtext("pubDate")
        parts = title.split(": ", 1)
        company, role = (parts[0], parts[1]) if len(parts) == 2 else ("Not specified", title)
        job = _normalise("We Work Remotely", link, role, company, link, description,
            "Remote; country eligibility not stated", "", pub,
            attribution_url="https://weworkremotely.com")
        if link and _matches_role(job):
            results.append(job)
    return results


def fetch_remotive():
    results = []
    for term in ROLE_TERMS:
        response = requests.get("https://remotive.com/api/remote-jobs",
            params={"search": term}, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        for item in response.json().get("jobs", []):
            loc = item.get("candidate_required_location") or "Not specified"
            job = _normalise("Remotive", item.get("id"), item.get("title"),
                item.get("company_name"), item.get("url"), item.get("description"),
                loc, item.get("job_type") or "", item.get("publication_date"),
                attribution_url="https://remotive.com")
            if job["url"] and _matches_role(job):
                results.append(job)
    return results


CONNECTORS = {
    "Himalayas": fetch_himalayas,
    "Remote OK": fetch_remoteok,
    "We Work Remotely": fetch_wwr,
    "Remotive": fetch_remotive,
}


def discover(selected_sources=None):
    """Return (jobs, errors); connector failures do not abort other sources."""
    jobs, errors = [], []
    for name in (selected_sources or list(CONNECTORS)):
        try:
            jobs.extend(CONNECTORS[name]())
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    # Deduplicate within this run by source + source job ID.
    unique = {}
    for job in jobs:
        unique[(job["source"], job["source_job_id"])] = job
    return list(unique.values()), errors
