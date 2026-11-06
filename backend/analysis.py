import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATASET_PATH = Path(__file__).resolve().parent / "dataset" / "product_reviews.csv"

ASPECTS: Dict[str, List[str]] = {
    "Battery": ["battery", "charge", "charging", "drains", "lasts"],
    "Camera": ["camera", "photo", "photos", "picture", "video", "recording", "focus"],
    "Performance": ["performance", "fast", "slow", "lag", "apps", "gaming", "games", "freeze"],
    "Price": ["price", "cost", "expensive", "cheap", "affordable", "value"],
    "Display": ["screen", "display", "brightness", "bright", "colours", "colors"],
    "Design & Build": ["design", "lightweight", "heavy", "build", "body", "sturdy", "buttons"],
    "Sound": ["speaker", "sound", "audio", "volume", "calls"],
    "Ease of Use": ["easy", "simple", "setup", "interface", "navigate", "use"]
}

_ANALYZER: Optional[SentimentIntensityAnalyzer] = None

def get_analyzer() -> SentimentIntensityAnalyzer:
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = SentimentIntensityAnalyzer()
    return _ANALYZER

def load_data(file_or_path: Optional[Any] = None) -> pd.DataFrame:
    path = file_or_path if file_or_path is not None else DATASET_PATH
    data = pd.read_csv(path)
    required = {"product_id", "review_text", "rating"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError("CSV needs columns: product_id, review_text, rating")
    data = data.dropna(subset=["product_id", "review_text"]).copy()
    data["product_id"] = data["product_id"].astype(str)
    data["review_text"] = data["review_text"].astype(str).str.strip()
    data["rating"] = pd.to_numeric(data["rating"], errors="coerce")
    return data.dropna(subset=["rating"]).query("review_text != ''")

def aspects_for(text: str) -> List[str]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return [name for name, keys in ASPECTS.items() if words.intersection(keys)]

def classify_sentiment(score: float) -> str:
    if score >= 0.05:
        return "Positive"
    elif score <= -0.05:
        return "Negative"
    return "Neutral"

def analyse(data: pd.DataFrame) -> pd.DataFrame:
    analyzer = get_analyzer()
    data = data.copy()
    data["sentiment_score"] = data["review_text"].apply(lambda x: analyzer.polarity_scores(x)["compound"])
    data["sentiment"] = data["sentiment_score"].apply(classify_sentiment)
    data["aspects"] = data["review_text"].apply(aspects_for)
    return data

def make_summary(
    data: pd.DataFrame,
    chosen: List[str],
    preference: str = "",
    count: int = 4
) -> Tuple[List[str], List[str], Optional[str]]:
    # Clamp count between 2 and 8
    count = max(2, min(8, int(count)))
    subset = data
    if chosen:
        subset = subset[subset["aspects"].apply(lambda tags: any(x in tags for x in chosen))]
    
    if subset.empty:
        return [], [], "No reviews mention those aspects. Try another selection."

    query = (" ".join(chosen) + " " + (preference or "")).strip()
    if not query:
        # If no aspects and no preference text, fallback to ranking by rating and sentiment
        ranked = subset.copy()
        ranked["relevance"] = 1.0
        ranked["rank"] = 0.65 * ranked["relevance"] + 0.15 * ranked["sentiment_score"].abs() + 0.20 * (ranked["rating"] / 5.0)
        good = ranked[ranked["sentiment"] == "Positive"].sort_values("rank", ascending=False).head(count)
        concerns = ranked[ranked["sentiment"] == "Negative"].sort_values("rank", ascending=False).head(count)
        return good["review_text"].tolist(), concerns["review_text"].tolist(), None

    corpus = subset["review_text"].tolist() + [query]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(corpus)
    similarity = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    
    subset = subset.copy()
    subset["relevance"] = similarity
    subset["rank"] = 0.65 * subset["relevance"] + 0.15 * subset["sentiment_score"].abs() + 0.20 * (subset["rating"] / 5.0)
    
    good = subset[subset["sentiment"] == "Positive"].sort_values("rank", ascending=False).head(count)
    concerns = subset[subset["sentiment"] == "Negative"].sort_values("rank", ascending=False).head(count)
    return good["review_text"].tolist(), concerns["review_text"].tolist(), None

