import re
import pandas as pd
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="Personalized Review Summarizer", page_icon="🛍️", layout="wide")
ASPECTS = {
    "Battery": ["battery", "charge", "charging", "drains", "lasts"],
    "Camera": ["camera", "photo", "photos", "picture", "video", "recording", "focus"],
    "Performance": ["performance", "fast", "slow", "lag", "apps", "gaming", "games", "freeze"],
    "Price": ["price", "cost", "expensive", "cheap", "affordable", "value"],
    "Display": ["screen", "display", "brightness", "bright", "colours", "colors"],
    "Design & Build": ["design", "lightweight", "heavy", "build", "body", "sturdy", "buttons"],
    "Sound": ["speaker", "sound", "audio", "volume", "calls"],
    "Ease of Use": ["easy", "simple", "setup", "interface", "navigate", "use"]
}
@st.cache_resource
def analyzer():
    return SentimentIntensityAnalyzer()

def load_data(file):
    data = pd.read_csv(file) if file else pd.read_csv("dataset/product_reviews.csv")
    required = {"product_id", "review_text", "rating"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError("CSV needs columns: product_id, review_text, rating")
    data = data.dropna(subset=["product_id", "review_text"]).copy()
    data["product_id"] = data["product_id"].astype(str)
    data["review_text"] = data["review_text"].astype(str).str.strip()
    data["rating"] = pd.to_numeric(data["rating"], errors="coerce")
    return data.dropna(subset=["rating"]).query("review_text != ''")

def aspects_for(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return [name for name, keys in ASPECTS.items() if words.intersection(keys)]

def analyse(data):
    a = analyzer()
    data = data.copy()
    data["sentiment_score"] = data.review_text.apply(lambda x: a.polarity_scores(x)["compound"])
    data["sentiment"] = data.sentiment_score.apply(
        lambda x: "Positive" if x >= .05 else ("Negative" if x <= -.05 else "Neutral"))
    data["aspects"] = data.review_text.apply(aspects_for)
    return data

def make_summary(data, chosen, preference, count):
    subset = data
    if chosen:
        subset = subset[subset.aspects.apply(lambda tags: any(x in tags for x in chosen))]
    if subset.empty:
        return [], [], "No reviews mention those aspects. Try another selection."
    query = " ".join(chosen) + " " + preference
    corpus = subset.review_text.tolist() + [query]
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(corpus)
    similarity = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    subset = subset.copy()
    subset["relevance"] = similarity
    subset["rank"] = .65 * subset.relevance + .15 * subset.sentiment_score.abs() + .20 * subset.rating / 5
    good = subset[subset.sentiment == "Positive"].sort_values("rank", ascending=False).head(count)
    concerns = subset[subset.sentiment == "Negative"].sort_values("rank", ascending=False).head(count)
    return good.review_text.tolist(), concerns.review_text.tolist(), None

st.title("🛍️ Personalized Product Review Summarizer")
st.write("Choose what matters to you and explore the review feedback that matches your priorities.")
with st.sidebar:
    st.header("Your preferences")
    chosen = st.multiselect("Important aspects", list(ASPECTS), ["Battery", "Camera"])
    preference = st.text_area("Your own priorities (optional)", placeholder="Example: I take photos and need long battery life.")
    count = st.slider("Review points per section", 2, 8, 4)

upload = st.file_uploader("Upload another review CSV (optional)", type=["csv"])
try:
    data = analyse(load_data(upload))
except Exception as e:
    st.error(str(e))
    st.stop()
if data.empty:
    st.warning("No valid review rows found.")
    st.stop()

product = st.selectbox("Product", sorted(data.product_id.unique()))
data = data[data.product_id == product]
a, b, c, d = st.columns(4)
a.metric("Reviews", len(data))
b.metric("Average rating", f"{data.rating.mean():.1f}/5")
c.metric("Positive reviews", int((data.sentiment == "Positive").sum()))
d.metric("Negative reviews", int((data.sentiment == "Negative").sum()))

st.subheader("Your personalized summary")
good, concerns, message = make_summary(data, chosen, preference, count)
if message:
    st.info(message)
else:
    left, right = st.columns(2)
    with left:
        st.markdown("#### Customers like")
        for item in good: st.success(item)
    with right:
        st.markdown("#### Customer concerns")
        for item in concerns: st.warning(item)

st.subheader("Sentiment overview")
st.bar_chart(data.sentiment.value_counts().reindex(["Positive", "Neutral", "Negative"], fill_value=0))
st.subheader("Explore reviews")
aspect = st.selectbox("Aspect filter", ["All"] + list(ASPECTS))
sent = st.selectbox("Sentiment filter", ["All", "Positive", "Neutral", "Negative"])
view = data
if aspect != "All": view = view[view.aspects.apply(lambda x: aspect in x)]
if sent != "All": view = view[view.sentiment == sent]
st.dataframe(view[["review_text", "rating", "sentiment", "aspects"]], use_container_width=True, hide_index=True)
st.download_button("Download analysed reviews", view[["product_id", "review_text", "rating", "sentiment"]].to_csv(index=False), "analysed_reviews.csv", "text/csv")
st.caption("Starter prototype: VADER estimates sentiment, keyword rules detect aspects, and TF-IDF ranks reviews against your preferences. The included reviews are synthetic examples, not real customer feedback.")
