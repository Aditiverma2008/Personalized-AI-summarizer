import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app import app
from analysis import (
    ASPECTS,
    load_data,
    aspects_for,
    classify_sentiment,
    analyse,
    make_summary
)
from review_scraper import validate_url_and_ip, ScrapeError, scrape_product_reviews

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "personalized-ai-summarizer-backend"

def test_load_bundled_dataset():
    df = load_data()
    assert not df.empty
    assert "product_id" in df.columns
    assert "review_text" in df.columns
    assert "rating" in df.columns
    assert len(df) == 100

def test_classify_sentiment():
    assert classify_sentiment(0.5) == "Positive"
    assert classify_sentiment(0.05) == "Positive"
    assert classify_sentiment(0.04) == "Neutral"
    assert classify_sentiment(-0.04) == "Neutral"
    assert classify_sentiment(-0.05) == "Negative"
    assert classify_sentiment(-0.8) == "Negative"

def test_aspects_for():
    text1 = "The battery lasts forever and charging is rapid."
    detected1 = aspects_for(text1)
    assert "Battery" in detected1

    text2 = "Takes terrible photos and has poor sound audio."
    detected2 = aspects_for(text2)
    assert "Camera" in detected2
    assert "Sound" in detected2

    text3 = "Unrelated words here."
    assert aspects_for(text3) == []

def test_analyse_and_summary():
    df = load_data()
    analysed = analyse(df)
    assert "sentiment_score" in analysed.columns
    assert "sentiment" in analysed.columns
    assert "aspects" in analysed.columns

    good, concerns, message = make_summary(analysed, chosen=["Battery", "Camera"], preference="long battery life", count=4)
    assert message is None
    assert len(good) <= 4
    assert len(concerns) <= 4

def test_summary_no_matching_aspects():
    df = pd.DataFrame([
        {"product_id": "p1", "review_text": "Good screen colors", "rating": 5, "aspects": ["Display"], "sentiment": "Positive", "sentiment_score": 0.8}
    ])
    good, concerns, msg = make_summary(df, chosen=["Sound"], preference="")
    assert "No reviews mention those aspects" in msg
    assert good == []
    assert concerns == []

def test_ssrf_protection():
    # Loopback IP
    with pytest.raises(ScrapeError):
        validate_url_and_ip("http://127.0.0.1/test")

    # Localhost
    with pytest.raises(ScrapeError):
        validate_url_and_ip("http://localhost:8000")

    # Private IP
    with pytest.raises(ScrapeError):
        validate_url_and_ip("http://192.168.1.1/admin")

    # Invalid scheme
    with pytest.raises(ScrapeError):
        validate_url_and_ip("ftp://example.com")

    # File scheme
    with pytest.raises(ScrapeError):
        validate_url_and_ip("file:///etc/passwd")

def test_api_analyze_bundled():
    payload = {
        "product_url": None,
        "aspects": ["Battery", "Camera"],
        "preference": "fast charging",
        "review_points": 3
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_reviews"] == 100
    assert data["average_rating"] > 0
    assert "sentiment_counts" in data
    assert data["sentiment_counts"]["positive"] > 0
    assert len(data["positive_highlights"]) <= 3
    assert len(data["negative_highlights"]) <= 3
    assert data["data_source"] == "bundled_csv"
    assert len(data["reviews"]) == 100

def test_api_analyze_ssrf_blocked():
    payload = {
        "product_url": "http://127.0.0.1:8080/secret",
        "aspects": ["Battery"],
        "preference": "",
        "review_points": 4
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 400
    assert "prohibited" in response.json()["detail"].lower() or "not permitted" in response.json()["detail"].lower()

@patch("review_scraper.safe_fetch")
def test_api_analyze_mocked_scraper(mock_fetch):
    mock_html = """
    <html>
      <body>
        <div data-hook="review">
          <span data-hook="review-body">The battery life is astonishing, lasts 2 full days without any lag.</span>
          <i data-hook="review-star-rating">5.0 out of 5 stars</i>
        </div>
        <div data-hook="review">
          <span data-hook="review-body">Terrible camera quality, pictures are blurry and night mode fails completely.</span>
          <i data-hook="review-star-rating">1.0 out of 5 stars</i>
        </div>
        <div data-hook="review">
          <span data-hook="review-body">Decent performance for games and daily use, but price feels slightly high.</span>
          <i data-hook="review-star-rating">3.0 out of 5 stars</i>
        </div>
      </body>
    </html>
    """
    mock_fetch.return_value = mock_html
    with patch("review_scraper.validate_url_and_ip"):
        payload = {
            "product_url": "https://example.com/product/123",
            "aspects": ["Battery", "Camera"],
            "preference": "battery",
            "review_points": 2
        }
        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_reviews"] == 3
        assert data["data_source"] == "scraped_url"
        assert len(data["positive_highlights"]) >= 1

