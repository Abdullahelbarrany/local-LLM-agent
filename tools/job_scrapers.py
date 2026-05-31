"""
Multi-site job scraper (Enhancements 1 & 2).

Each scraper method returns normalized job dicts:
  {title, company, location, url, description, date_posted, source}

Sites with public JSON APIs (Remotive, Jobicy) are the most reliable.
HTML scrapers (Wuzzuf, WeWorkRemotely, Bayt, Naukrigulf) work with best-effort parsing.
JS-heavy sites (Otta, Himalayas, Wellfound) fall back to DuckDuckGo site: search.
Heavily guarded sites (LinkedIn, Indeed, Glassdoor) are attempted but often blocked.
"""

import logging
import random
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_TIMEOUT = 15.0
_RATE_DELAY = (1.0, 2.0)
_MAX_WORKERS = 5  # parallel scraper threads
_PER_SOURCE_LIMIT = 15  # target results per source


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _norm(text: str) -> str:
    """Lowercase + strip punctuation — used for deduplication key."""
    return text.lower().translate(str.maketrans("", "", string.punctuation)).strip()


def _bs(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _get(url: str, params: dict | None = None) -> httpx.Response:
    headers = {
        "User-Agent": _random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
    }
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
        return client.get(url, params=params)


def _safe(name: str, fn) -> list[dict]:
    """Apply rate delay, run fn(), catch and log all exceptions."""
    try:
        time.sleep(random.uniform(*_RATE_DELAY))
        result = fn()
        logger.info("Scraper [%s] → %d jobs", name, len(result))
        return result
    except Exception as exc:
        logger.warning("Scraper [%s] failed: %s", name, exc)
        return []


class JobScraper:
    """Multi-site job scraper. All methods are synchronous (run in thread pool)."""

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    def scrape_linkedin(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get(
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                {"keywords": query, "location": location or "Remote", "start": 0, "count": _PER_SOURCE_LIMIT, "f_WT": 2},
            )
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select("li"):
                title_el   = card.select_one(".base-search-card__title")
                company_el = card.select_one(".base-search-card__subtitle a")
                loc_el     = card.select_one(".job-search-card__location")
                link_el    = card.select_one("a.base-card__full-link")
                date_el    = card.select_one("time")
                if not (title_el and link_el):
                    continue
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         link_el["href"].split("?")[0],
                    "description": "",
                    "date_posted": date_el.get("datetime", "") if date_el else "",
                    "source":      "LinkedIn",
                })
            return jobs
        return _safe("LinkedIn", _fn)

    # ── Indeed ────────────────────────────────────────────────────────────────
    def scrape_indeed(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get("https://www.indeed.com/jobs", {"q": query, "l": location})
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select("[data-jk]"):
                title_el   = card.select_one("[class*='jobTitle']")
                company_el = card.select_one("[data-testid='company-name']")
                loc_el     = card.select_one("[data-testid='text-location']")
                snippet_el = card.select_one("[class*='job-snippet']")
                jk = card.get("data-jk", "")
                if not (title_el and jk):
                    continue
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         f"https://www.indeed.com/viewjob?jk={jk}",
                    "description": snippet_el.get_text(strip=True) if snippet_el else "",
                    "date_posted": "",
                    "source":      "Indeed",
                })
            return jobs
        return _safe("Indeed", _fn)

    # ── Glassdoor ─────────────────────────────────────────────────────────────
    def scrape_glassdoor(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get(
                "https://www.glassdoor.com/Job/jobs.htm",
                {"sc.keyword": query, "locT": "N"},
            )
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select("li[data-test='jobListing']"):
                title_el   = card.select_one("[data-test='job-link']")
                company_el = card.select_one("[data-test='employer-name']")
                loc_el     = card.select_one("[data-test='emp-location']")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                url  = f"https://www.glassdoor.com{href}" if href.startswith("/") else href
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         url,
                    "description": "",
                    "date_posted": "",
                    "source":      "Glassdoor",
                })
            return jobs
        return _safe("Glassdoor", _fn)

    # ── Wuzzuf ────────────────────────────────────────────────────────────────
    def scrape_wuzzuf(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get("https://wuzzuf.net/search/jobs/", {"q": query, "l": location})
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select("article[data-job-id]"):
                title_el   = card.select_one("h2 a")
                company_el = card.select_one("a[data-analytics='job-company']")
                loc_el     = card.select_one(".css-5wys0k")
                date_el    = card.select_one("time")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                url  = f"https://wuzzuf.net{href}" if href.startswith("/") else href
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         url,
                    "description": "",
                    "date_posted": date_el.get("datetime", "") if date_el else "",
                    "source":      "Wuzzuf",
                })
            return jobs
        return _safe("Wuzzuf", _fn)

    # ── Bayt ──────────────────────────────────────────────────────────────────
    def scrape_bayt(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            slug = re.sub(r"\s+", "-", query.lower().strip())
            resp = _get(f"https://www.bayt.com/en/international/jobs/{slug}-jobs/")
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select("li[data-js-job-id]"):
                title_el   = card.select_one("h2 a")
                company_el = card.select_one("[class*='jb-company']")
                loc_el     = card.select_one("[class*='jb-loc']")
                date_el    = card.select_one("[class*='jb-date']")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                url  = f"https://www.bayt.com{href}" if href.startswith("/") else href
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         url,
                    "description": "",
                    "date_posted": date_el.get_text(strip=True) if date_el else "",
                    "source":      "Bayt",
                })
            return jobs
        return _safe("Bayt", _fn)

    # ── Naukrigulf ────────────────────────────────────────────────────────────
    def scrape_naukrigulf(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            slug = re.sub(r"\s+", "-", query.lower().strip())
            resp = _get(f"https://www.naukrigulf.com/{slug}-jobs")
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for card in soup.select(".ni-job-tuple, [class*='job-tuple']"):
                title_el   = card.select_one("a.title, .title a")
                company_el = card.select_one(".company-name, [class*='company']")
                loc_el     = card.select_one(".location-li, [class*='location']")
                date_el    = card.select_one(".job-post-day, [class*='date']")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                url  = href if href.startswith("http") else f"https://www.naukrigulf.com{href}"
                jobs.append({
                    "title":       title_el.get_text(strip=True),
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         url,
                    "description": "",
                    "date_posted": date_el.get_text(strip=True) if date_el else "",
                    "source":      "Naukrigulf",
                })
            return jobs
        return _safe("Naukrigulf", _fn)

    # ── Remotive (public JSON API) ─────────────────────────────────────────────
    def scrape_remotive(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get(
                "https://remotive.com/api/remote-jobs",
                {"search": query, "limit": _PER_SOURCE_LIMIT},
            )
            data = resp.json()
            jobs: list[dict] = []
            for job in data.get("jobs", [])[:_PER_SOURCE_LIMIT]:
                jobs.append({
                    "title":       job.get("title", ""),
                    "company":     job.get("company_name", ""),
                    "location":    job.get("candidate_required_location", "Remote"),
                    "url":         job.get("url", ""),
                    "description": _strip_html(job.get("description", ""))[:500],
                    "date_posted": job.get("publication_date", ""),
                    "source":      "Remotive",
                })
            return jobs
        return _safe("Remotive", _fn)

    # ── WeWorkRemotely ────────────────────────────────────────────────────────
    def scrape_weworkremotely(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get(
                "https://weworkremotely.com/remote-jobs/search",
                {"term": query},
            )
            soup = _bs(resp.text)
            jobs: list[dict] = []
            for section in soup.select("section.jobs"):
                for card in section.select("article"):
                    title_el   = card.select_one("span.title")
                    company_el = card.select_one("span.company")
                    region_el  = card.select_one("span.region")
                    link_el    = card.select_one("a")
                    if not (title_el and link_el):
                        continue
                    href = link_el.get("href", "")
                    url  = f"https://weworkremotely.com{href}" if href.startswith("/") else href
                    jobs.append({
                        "title":       title_el.get_text(strip=True),
                        "company":     company_el.get_text(strip=True) if company_el else "",
                        "location":    region_el.get_text(strip=True) if region_el else "Remote",
                        "url":         url,
                        "description": "",
                        "date_posted": "",
                        "source":      "WeWorkRemotely",
                    })
            return jobs
        return _safe("WeWorkRemotely", _fn)

    # ── Jobicy (public JSON API) ───────────────────────────────────────────────
    def scrape_jobicy(self, query: str, location: str = "") -> list[dict]:
        def _fn() -> list[dict]:
            resp = _get(
                "https://jobicy.com/api/v2/remote-jobs",
                {"search": query, "count": _PER_SOURCE_LIMIT},
            )
            data = resp.json()
            jobs: list[dict] = []
            for job in data.get("jobs", [])[:_PER_SOURCE_LIMIT]:
                jobs.append({
                    "title":       job.get("jobTitle", ""),
                    "company":     job.get("companyName", ""),
                    "location":    job.get("jobGeo", "Remote"),
                    "url":         job.get("url", ""),
                    "description": _strip_html(job.get("jobDescription", ""))[:500],
                    "date_posted": job.get("pubDate", ""),
                    "source":      "Jobicy",
                })
            return jobs
        return _safe("Jobicy", _fn)

    # ── DDG-backed fallbacks for JS-heavy sites ───────────────────────────────
    _LISTING_PAGE_RE = re.compile(
        r"(jobs?\s+in\s+\d{4}|jobs?\s+listing|remote\s+jobs?\s*\||\bjobs?\s*\|)",
        re.IGNORECASE,
    )
    _AT_COMPANY_RE = re.compile(r"\bat\s+([^|·•\n]+?)(?:\s*[|·•]|\s*$)", re.IGNORECASE)

    def _ddg_fallback(self, site: str, jobs_subpath: str, query: str, label: str,
                      min_path_depth: int = 2) -> list[dict]:
        def _fn() -> list[dict]:
            from urllib.parse import urlparse
            from ddgs import DDGS
            # Restrict search to the /jobs/ subpath so we get individual listings
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    f'site:{site}/{jobs_subpath} "{query}" remote',
                    max_results=15,
                ))
            jobs: list[dict] = []
            for r in results:
                url   = r.get("href", "")
                title = r.get("title", "").strip()
                if not url.startswith("http"):
                    continue
                # Skip category / search-results pages
                path_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
                if len(path_parts) < min_path_depth:
                    continue
                if self._LISTING_PAGE_RE.search(title):
                    continue
                # Try to pull company from "Title at Company · …" format
                company = ""
                m = self._AT_COMPANY_RE.search(title)
                if m:
                    company = m.group(1).strip()
                    title   = title[: m.start()].strip(" -–|")
                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    "Remote",
                    "url":         url,
                    "description": r.get("body", ""),
                    "date_posted": "",
                    "source":      label,
                })
            return jobs[:8]
        return _safe(label, _fn)

    def scrape_otta(self, query: str, location: str = "") -> list[dict]:
        return self._ddg_fallback("app.otta.com", "jobs", query, "Otta", min_path_depth=2)

    def scrape_himalayas(self, query: str, location: str = "") -> list[dict]:
        return self._ddg_fallback("himalayas.app", "jobs", query, "Himalayas", min_path_depth=3)

    def scrape_wellfound(self, query: str, location: str = "") -> list[dict]:
        return self._ddg_fallback("wellfound.com", "jobs", query, "Wellfound", min_path_depth=2)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    def scrape_all(self, query: str, location: str = "") -> list[dict]:
        """Run all scrapers in parallel (up to _MAX_WORKERS threads).

        API-backed scrapers are listed first so they land in the first batch.
        """
        scrapers = [
            self.scrape_remotive,        # JSON API — most reliable
            self.scrape_jobicy,          # JSON API — most reliable
            self.scrape_wuzzuf,          # Egypt/MENA HTML
            self.scrape_weworkremotely,  # Remote HTML
            self.scrape_bayt,            # MENA HTML
            self.scrape_naukrigulf,      # Gulf HTML
            self.scrape_linkedin,        # often returns challenge page
            self.scrape_indeed,          # often returns filtered results
            self.scrape_glassdoor,       # very often blocked
            self.scrape_otta,            # DDG fallback
            self.scrape_himalayas,       # DDG fallback
            self.scrape_wellfound,       # DDG fallback
        ]
        all_jobs: list[dict] = []
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(fn, query, location): fn.__name__ for fn in scrapers}
            for future in as_completed(futures):
                try:
                    all_jobs.extend(future.result())
                except Exception as exc:
                    logger.warning("Scraper thread error: %s", exc)
        return all_jobs


# ── Enhancement 2: Deduplication ──────────────────────────────────────────────

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """Remove duplicate postings by normalised (company, title) key.

    Keeps the first occurrence of each unique (company, title) pair.
    Empty-key entries (both company and title missing) are dropped.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        key = _norm(job.get("company", "")) + "|" + _norm(job.get("title", ""))
        if key == "|":
            continue
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ── Enhancement 2: Relevance scoring ─────────────────────────────────────────

def score_job_relevance(job: dict, cv_keywords: list[str]) -> float:
    """Return a 0.0–1.0 score: fraction of cv_keywords found in title+description.

    Uses TF presence (keyword present/absent), not TF-IDF, for speed.
    Returns 0.5 when no keywords are provided (neutral baseline).
    """
    if not cv_keywords:
        return 0.5
    text = (
        job.get("title", "") + " " + job.get("description", "")
    ).lower()
    matched = sum(1 for kw in cv_keywords if kw.lower() in text)
    return round(matched / len(cv_keywords), 4)
