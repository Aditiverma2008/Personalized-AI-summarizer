# Personalized Review Summarization

A beginner-friendly Python AI/NLP prototype that analyses product reviews and highlights feedback according to a customer's selected priorities.

## Features
- Includes a CSV with 100 synthetic sample reviews.
- Lets users select review aspects: battery, camera, performance, price, display, design/build, sound, and ease of use.
- Estimates positive, neutral, and negative sentiment using VADER.
- Uses TF-IDF and cosine similarity to rank reviews against the selected preferences.
- Shows positive points and customer concerns separately.
- Paste a **Flipkart** product link to analyse its live reviews (top reviews plus negative-first, up to 50). Other sites work only if their HTML includes schema.org review data.
- Download analysed reviews as CSV.

## Dataset
`dataset/product_reviews.csv` has 100 synthetic sample reviews and these required columns:
- `product_id`
- `review_text`
- `rating`

## Run the project
Install Python 3.10 or newer. Open a terminal in this project folder and run:

```bash
python -m venv .venv
```

Activate the environment:

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install dependencies and launch:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown in the terminal (usually http://localhost:8501).

## How the prototype works
1. Preprocessing checks the required columns and removes incomplete rows.
2. Keyword rules identify aspects mentioned in each review.
3. VADER estimates review sentiment.
4. TF-IDF converts review text and preference text into vectors.
5. Cosine similarity estimates relevance to the user's preferences.
6. The app ranks and displays positive and negative review statements.

## Limitations
- The included reviews are synthetic examples for development, not real customer feedback.
- Aspect detection uses a small keyword dictionary and may miss synonyms or context.
- Sentiment tools can misunderstand sarcasm and mixed opinions.
- This baseline selects review statements; it does not train a custom model or generate new abstractive text.
- Verify generated insights against original reviews and do not upload identifying customer information.

## Possible next steps
Test with a real, appropriately licensed dataset; expand the aspect vocabulary; evaluate relevance and factual support; and consider adding a grounded language model for abstractive summaries.
