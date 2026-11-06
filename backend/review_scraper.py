import ipaddress
import json
import re
import socket
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

class ScrapeError(Exception):
    """Raised when web scraping fails or an invalid URL is provided."""
    pass

# Maximum content size: 5 MB
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 10
MAX_REDIRECTS = 5
MAX_REVIEWS = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def validate_url_and_ip(url: str) -> None:
    """
    Validates scheme and ensures host does not resolve to private, loopback,
    link-local, multicast, or reserved IP addresses to prevent SSRF.
    """
    if not url or not isinstance(url, str):
        raise ScrapeError("Invalid URL: must be a non-empty string.")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ScrapeError("Invalid URL scheme: only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ScrapeError("Invalid URL: missing hostname.")

    # Disallow known localhost aliases
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        raise ScrapeError(f"Access to '{hostname}' is not permitted.")

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ScrapeError(f"Could not resolve host '{hostname}': {str(e)}")

    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)

        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ScrapeError(f"Access to private or restricted network address ({ip_str}) is prohibited.")

def safe_fetch(url: str) -> str:
    """
    Fetches the URL content with manual redirect tracking, SSRF validation at every hop,
    and size limits.
    """
    current_url = url
    session = requests.Session()
    session.headers.update(HEADERS)

    for _ in range(MAX_REDIRECTS):
        validate_url_and_ip(current_url)

        try:
            with session.get(current_url, timeout=DEFAULT_TIMEOUT, allow_redirects=False, stream=True) as resp:
                if resp.is_redirect or resp.is_permanent_redirect or 300 <= resp.status_code < 400:
                    redirect_location = resp.headers.get("Location")
                    if not redirect_location:
                        raise ScrapeError("Redirect missing Location header.")
                    current_url = urljoin(current_url, redirect_location)
                    continue

                if resp.status_code != 200:
                    raise ScrapeError(f"HTTP error {resp.status_code} when loading URL.")

                content_len_header = resp.headers.get("Content-Length")
                if content_len_header and int(content_len_header) > MAX_RESPONSE_BYTES:
                    raise ScrapeError("Response size exceeds the allowable limit (5MB).")

                chunks = []
                total_bytes = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_RESPONSE_BYTES:
                        raise ScrapeError("Response size exceeds the allowable limit (5MB).")
                    chunks.append(chunk)

                encoding = resp.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")

        except requests.exceptions.Timeout:
            raise ScrapeError("Request timed out while trying to fetch the webpage.")
        except requests.exceptions.RequestException as e:
            raise ScrapeError(f"Network error while fetching the webpage: {str(e)}")

    raise ScrapeError("Too many redirects.")

def extract_from_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews = []
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except Exception:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            # Look for review objects or product with review
            raw_reviews = []
            if item.get("@type") == "Review":
                raw_reviews.append(item)
            elif "review" in item:
                rev_val = item["review"]
                if isinstance(rev_val, list):
                    raw_reviews.extend(rev_val)
                elif isinstance(rev_val, dict):
                    raw_reviews.append(rev_val)

            for r in raw_reviews:
                text = r.get("reviewBody") or r.get("description")
                if not text or not isinstance(text, str):
                    continue
                rating = 4.0
                if "reviewRating" in r and isinstance(r["reviewRating"], dict):
                    rating_val = r["reviewRating"].get("ratingValue")
                    try:
                        rating = float(rating_val)
                    except (ValueError, TypeError):
                        pass
                reviews.append({
                    "review_text": text.strip(),
                    "rating": rating
                })
    return reviews

def extract_from_microdata(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews = []
    review_items = soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Review", re.I)})
    for item in review_items:
        body_elem = item.find(attrs={"itemprop": "reviewBody"}) or item.find(attrs={"itemprop": "description"})
        if not body_elem:
            continue
        text = body_elem.get_text(separator=" ", strip=True)
        if not text:
            continue

        rating = 4.0
        rating_elem = item.find(attrs={"itemprop": "ratingValue"})
        if rating_elem:
            val = rating_elem.get("content") or rating_elem.get_text(strip=True)
            try:
                rating = float(val)
            except (ValueError, TypeError):
                pass
        reviews.append({"review_text": text, "rating": rating})
    return reviews

def extract_amazon_reviews(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews = []
    review_divs = soup.find_all("div", {"data-hook": "review"})
    for div in review_divs:
        body = div.find("span", {"data-hook": "review-body"})
        if not body:
            continue
        text = body.get_text(separator=" ", strip=True)
        if not text:
            continue

        rating = 4.0
        star_span = div.find("i", {"data-hook": "review-star-rating"}) or div.find("i", {"data-hook": "cmps-review-star-rating"})
        if star_span:
            star_text = star_span.get_text(strip=True)
            match = re.search(r"(\d+(\.\d+)?)", star_text)
            if match:
                try:
                    rating = float(match.group(1))
                except ValueError:
                    pass
        reviews.append({"review_text": text, "rating": rating})
    return reviews

def extract_flipkart_reviews(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews = []
    # Flipkart review containers often have row/comment cards with star badge
    containers = soup.find_all("div", class_=re.compile(r"cPHDOP|col-12-12|_1AtVbE|EKKjF|row"))
    for c in containers:
        text_elem = c.find("div", class_=re.compile(r"t-ZTKy|ZmyHeo|_1mXdtf"))
        if not text_elem:
            continue
        text = text_elem.get_text(separator=" ", strip=True)
        # Clean Flipkart's "READ MORE" button text
        text = re.sub(r"READ MORE$", "", text, flags=re.I).strip()
        if not text or len(text) < 10:
            continue

        rating = 4.0
        star_elem = c.find("div", class_=re.compile(r"XQDdHH|_3LWZlK|hGSR34"))
        if star_elem:
            match = re.search(r"(\d+(\.\d+)?)", star_elem.get_text(strip=True))
            if match:
                try:
                    rating = float(match.group(1))
                except ValueError:
                    pass
        reviews.append({"review_text": text, "rating": rating})
    return reviews

def extract_generic_reviews(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews = []
    # Generic search for elements whose class or id includes 'review'
    elements = soup.find_all(["div", "article", "li"], class_=re.compile(r"review|comment|testimonial", re.I))
    for el in elements:
        text = el.get_text(separator=" ", strip=True)
        if 40 <= len(text) <= 1500:
            # Check for stars or ratings
            rating = 4.0
            match = re.search(r"(\d+(\.\d+)?)\s*(?:out of 5|/5|stars?)", text, re.I)
            if match:
                try:
                    rating = min(5.0, float(match.group(1)))
                except ValueError:
                    pass
            reviews.append({"review_text": text, "rating": rating})
    return reviews

def scrape_product_reviews(url: str, max_reviews: int = MAX_REVIEWS) -> List[Dict[str, Any]]:
    """
    Fetches the given URL and parses reviews using multiple extraction strategies:
    1. Flipkart-specific parser
    2. Amazon parser
    3. JSON-LD structured data
    4. Microdata
    5. Generic heuristics
    """
    html = safe_fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    results: List[Dict[str, Any]] = []

    domain = urlparse(url).netloc.lower()
    if "flipkart" in domain:
        results = extract_flipkart_reviews(soup)
    elif "amazon" in domain:
        results = extract_amazon_reviews(soup)

    if not results:
        results = extract_from_json_ld(soup)

    if not results:
        results = extract_from_microdata(soup)

    if not results:
        results = extract_amazon_reviews(soup)

    if not results:
        results = extract_flipkart_reviews(soup)

    if not results:
        results = extract_generic_reviews(soup)

    # Deduplicate by text
    seen = set()
    cleaned = []
    for r in results:
        txt = r["review_text"].strip()
        if txt and txt not in seen and len(txt) >= 15:
            seen.add(txt)
            cleaned.append({
                "product_id": domain or "product",
                "review_text": txt,
                "rating": float(r.get("rating", 4.0))
            })
            if len(cleaned) >= max_reviews:
                break

    if not cleaned:
        raise ScrapeError(
            "Could not extract any product reviews from this webpage. "
            "The site may require JavaScript, utilize anti-bot verification, or lack standard review markup."
        )

    return cleaned

