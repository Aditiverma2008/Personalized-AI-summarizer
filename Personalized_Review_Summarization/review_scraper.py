"""Fetch customer reviews from a product page URL.

Flipkart links are handled by a dedicated scraper (flipkart.com/product-reviews
pages embed all reviews as JSON, 10 per page, no login needed).

For every other site, strategies are tried in order until one returns reviews:
  1. schema.org JSON-LD  (Product -> review[])     - works on many shops
  2. Microdata           (itemprop="reviewBody")
  3. Amazon markup       (data-hook="review")
  4. Generic fallback    (elements whose class mentions "review" + body/text)

Many big retailers (Amazon, Flipkart...) render reviews with JavaScript or block
bots, so a plain HTTP fetch can legitimately return nothing. The app then asks
a clear error is shown.
"""
import json
import re
import time
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}


class ScrapeError(Exception):
    pass


def _num(value):
    m = re.search(r"\d+(\.\d+)?", str(value or ""))
    return float(m.group()) if m else None


def _walk(node):
    """Yield every dict inside a JSON-LD structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _from_jsonld(soup):
    rows = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for obj in _walk(data):
            reviews = obj.get("review")
            if isinstance(reviews, dict):
                reviews = [reviews]
            for r in reviews or []:
                if not isinstance(r, dict):
                    continue
                text = r.get("reviewBody") or r.get("description")
                rating = r.get("reviewRating")
                rating = _num(rating.get("ratingValue") if isinstance(rating, dict) else rating)
                if text and rating is not None:
                    rows.append((text, rating))
    return rows


def _from_microdata(soup):
    rows = []
    for body in soup.select('[itemprop="reviewBody"]'):
        container = body.find_parent(attrs={"itemtype": re.compile("Review")}) or body.parent
        rating_el = container.select_one('[itemprop="ratingValue"]') if container else None
        rating = _num(rating_el.get("content") or rating_el.get_text()) if rating_el else None
        if rating is not None:
            rows.append((body.get_text(" ", strip=True), rating))
    return rows


def _from_amazon(soup):
    rows = []
    for rev in soup.select('[data-hook="review"]'):
        body = rev.select_one('[data-hook="review-body"]')
        star = rev.select_one('[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]')
        rating = _num(star.get_text()) if star else None
        if body and rating is not None:
            rows.append((body.get_text(" ", strip=True), rating))
    return rows


def _from_generic(soup):
    rows = []
    for el in soup.find_all(class_=re.compile(r"review[-_ ]?(body|text|content)", re.I)):
        text = el.get_text(" ", strip=True)
        scope = el.find_parent(class_=re.compile("review", re.I)) or el.parent
        rating = None
        if scope:
            for cand in scope.find_all(attrs={"aria-label": re.compile(r"\d.*(star|out of)", re.I)}):
                rating = _num(cand["aria-label"])
                break
            if rating is None:
                for cand in scope.find_all(class_=re.compile(r"(rating|star)", re.I)):
                    rating = _num(cand.get_text() or cand.get("title") or cand.get("data-rating"))
                    if rating is not None:
                        break
        if text and rating is not None:
            rows.append((text, rating))
    return rows


# ---------------------------------------------------------------- Flipkart
_STATE_MARK = "window.__INITIAL_STATE__ ="


def _is_flipkart(netloc):
    return netloc == "flipkart.com" or netloc.endswith(".flipkart.com")


def _flipkart_ids(url):
    """Return (path_prefix, item_id, pid) from a Flipkart product link."""
    parsed = urlparse(url)
    m = re.search(r"^(.*?)/(?:p|product-reviews)/(itm[a-z0-9]+)", parsed.path)
    pid = re.search(r"(?:^|&)pid=([A-Z0-9]+)", parsed.query)
    if not m or not pid:
        raise ScrapeError("This Flipkart link is missing the product id. Open the product page "
                          "and copy the full link (it contains /p/itm... and ?pid=...).")
    return m.group(1), m.group(2), pid.group(1)


def _walk_reviews(node, out):
    if isinstance(node, dict):
        if node.get("type") == "ProductReviewValue":
            out.append(node)
        for v in node.values():
            _walk_reviews(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_reviews(v, out)
    return out


def _flipkart_page(session, url, timeout):
    resp = session.get(url, headers=HEADERS, timeout=timeout)
    if resp.status_code >= 400:
        raise ScrapeError(f"Flipkart refused the request (HTTP {resp.status_code}).")
    i = resp.text.find(_STATE_MARK)
    if i == -1:
        return [], ""
    try:
        state, _ = json.JSONDecoder().raw_decode(resp.text[i + len(_STATE_MARK):].lstrip())
    except ValueError:
        return [], ""
    title = re.search(r"<title>(.*?)</title>", resp.text, re.S)
    return _walk_reviews(state, []), (title.group(1) if title else "")


def _fetch_flipkart(url, max_pages, timeout):
    """Pull top reviews plus negative-first reviews so both sides are represented."""
    prefix, item, pid = _flipkart_ids(url)
    session = requests.Session()
    top_pages = max(1, (max_pages * 3) // 5)
    plan = [("", p) for p in range(1, top_pages + 1)] + \
           [("&sortOrder=NEGATIVE_FIRST", p) for p in range(1, max_pages - top_pages + 1)]
    rows, title = [], ""
    for sort, page in plan:
        page_url = (f"https://www.flipkart.com{prefix}/product-reviews/{item}"
                    f"?pid={pid}&page={page}{sort}")
        found, page_title = _flipkart_page(session, page_url, timeout)
        title = title or page_title
        for r in found:
            text = " ".join(filter(None, [r.get("title"), r.get("text")])).strip()
            rating = _num(r.get("rating"))
            if text and rating is not None:
                rows.append((text, rating))
        time.sleep(0.8)  # be polite
    name = re.sub(r"\s*(Reviews:|Online at|\|).*$", "", title).strip() or item
    return rows, name


STRATEGIES = [_from_jsonld, _from_microdata, _from_amazon, _from_generic]


def fetch_reviews(url, timeout=15, max_pages=5):
    """Return a DataFrame with product_id, review_text, rating."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ScrapeError("That doesn't look like a valid URL.")
    if _is_flipkart(parsed.netloc.lower()):
        try:
            rows, name = _fetch_flipkart(url, max_pages, timeout)
        except requests.RequestException as e:
            raise ScrapeError(f"Could not reach Flipkart: {e.__class__.__name__}") from e
        if not rows:
            raise ScrapeError("No reviews found for this Flipkart product (it may have none yet).")
        df = pd.DataFrame(rows, columns=["review_text", "rating"]).drop_duplicates("review_text")
        df.insert(0, "product_id", name[:60])
        return df

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.RequestException as e:
        raise ScrapeError(f"Could not open the page: {e.__class__.__name__}") from e
    if resp.status_code >= 400:
        raise ScrapeError(f"The site refused the request (HTTP {resp.status_code}). "
                          "It probably blocks automated access.")

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for strategy in STRATEGIES:
        rows = strategy(soup)
        if rows:
            break
    if not rows:
        raise ScrapeError("No reviews found in the page HTML. The site may load reviews with "
                          "JavaScript or block bots. Try a reviews-page link, or try another link.")

    title = soup.title.get_text(strip=True) if soup.title else parsed.netloc
    name = title[:60] or parsed.netloc
    df = pd.DataFrame(rows, columns=["review_text", "rating"]).drop_duplicates("review_text")
    df.insert(0, "product_id", name)
    return df
