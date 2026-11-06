import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
import pandas as pd

from analysis import (
    ASPECTS,
    load_data,
    analyse,
    make_summary,
    classify_sentiment
)
from review_scraper import scrape_product_reviews, ScrapeError

app = FastAPI(
    title="Personalized AI Review Summarizer API",
    description="Backend API for sentiment analysis and aspect-based review ranking",
    version="1.0.0"
)

# Configure CORS
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env.strip():
    allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    product_url: Optional[str] = Field(default=None, max_length=1000)
    aspects: List[str] = Field(default_factory=lambda: ["Battery", "Camera"])
    preference: Optional[str] = Field(default="", max_length=500)
    review_points: int = Field(default=4, ge=2, le=8)

class ReviewRecord(BaseModel):
    product_id: str
    review_text: str
    rating: float
    sentiment_score: float
    sentiment: str
    aspects: List[str]

class SentimentCounts(BaseModel):
    positive: int
    neutral: int
    negative: int

class AnalyzeResponse(BaseModel):
    total_reviews: int
    average_rating: float
    sentiment_counts: SentimentCounts
    positive_highlights: List[str]
    negative_highlights: List[str]
    reviews: List[ReviewRecord]
    info_message: Optional[str] = None
    data_source: str

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "personalized-ai-summarizer-backend",
        "version": "1.0.0"
    }

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_reviews(payload: AnalyzeRequest):
    url = (payload.product_url or "").strip()
    data_source = "bundled_csv"

    # Step 1: Obtain review DataFrame
    if url:
        try:
            scraped_data = scrape_product_reviews(url)
            df = pd.DataFrame(scraped_data)
            data_source = "scraped_url"
        except ScrapeError as se:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(se)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while scraping the product reviews: {str(e)}"
            )
    else:
        try:
            df = load_data()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load dataset: {str(e)}"
            )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid review records found to analyse."
        )

    # Step 2: Run sentiment & aspect analysis
    analysed_df = analyse(df)

    # Step 3: Compute summary highlights according to preferences
    chosen_aspects = [a for a in payload.aspects if a in ASPECTS]
    pref_text = (payload.preference or "").strip()
    good, concerns, message = make_summary(
        analysed_df,
        chosen=chosen_aspects,
        preference=pref_text,
        count=payload.review_points
    )

    # Step 4: Aggregate metrics
    total_reviews = len(analysed_df)
    avg_rating = round(float(analysed_df["rating"].mean()), 2)
    pos_count = int((analysed_df["sentiment"] == "Positive").sum())
    neu_count = int((analysed_df["sentiment"] == "Neutral").sum())
    neg_count = int((analysed_df["sentiment"] == "Negative").sum())

    # Build review list
    records: List[ReviewRecord] = []
    for _, row in analysed_df.iterrows():
        records.append(
            ReviewRecord(
                product_id=str(row["product_id"]),
                review_text=str(row["review_text"]),
                rating=float(row["rating"]),
                sentiment_score=round(float(row["sentiment_score"]), 4),
                sentiment=str(row["sentiment"]),
                aspects=list(row["aspects"])
            )
        )

    return AnalyzeResponse(
        total_reviews=total_reviews,
        average_rating=avg_rating,
        sentiment_counts=SentimentCounts(
            positive=pos_count,
            neutral=neu_count,
            negative=neg_count
        ),
        positive_highlights=good,
        negative_highlights=concerns,
        reviews=records,
        info_message=message,
        data_source=data_source
    )

