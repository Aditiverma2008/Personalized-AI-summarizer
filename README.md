# Personalized AI Review Summarizer

A production-ready product review analysis dashboard powered by **FastAPI** (Python) on the backend and **Next.js / React / TypeScript** on the frontend, structured for seamless deployment onto **Vercel** as two independent projects from the same GitHub repository.

---

## 💡 What the Application Does

The Personalized Review Summarizer allows shoppers to inspect customer feedback tailored directly to their individual priorities (e.g., *battery life, camera quality, gaming performance, price value*):

- **Personalized Highlights:** Extrapolates key positive highlights ("Customers Like") and concerns ("Customer Concerns") ranked according to selected aspects and custom user priorities.
- **Sentiment Classification:** Computes polarity metrics (Positive, Neutral, Negative) across all reviews.
- **Aspect Extraction:** Identifies category mentions (Battery, Camera, Performance, Price, Display, Design & Build, Sound, Ease of Use).
- **Review Explorer & Filtering:** Filter, inspect, and export reviews with associated metadata and ratings.
- **Data Ingestion:** Supports analyzing bundled synthetic reviews or scraping live e-commerce product pages with built-in SSRF protection.

> **Methodology Note:** Summarization is performed using **VADER sentiment analysis**, **keyword aspect tagging**, and **TF-IDF cosine similarity review ranking** against user preferences. It is an extractive aspect-ranking system and does not rely on costly external LLMs or third-party paid AI APIs.

---

## 🏗️ Architecture

```text
Personalized-AI-summarizer/
├── frontend/               # Next.js (App Router, TypeScript)
│   ├── app/                # Pages and layouts
│   ├── components/         # Reusable UI elements
│   ├── lib/                # API client, CSV exporter, types
│   ├── public/             # Static assets
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── .env.example
│
├── backend/                # FastAPI (ASGI, Python 3)
│   ├── api/index.py        # Vercel Serverless Function entrypoint
│   ├── app.py              # FastAPI application & endpoints
│   ├── analysis.py         # Sentiment, TF-IDF ranking, aspect rules
│   ├── review_scraper.py   # Multi-strategy scraper with SSRF protections
│   ├── requirements.txt    # Backend dependencies
│   ├── dataset/
│   │   └── product_reviews.csv
│   └── tests/              # Pytest test suite
│
├── README.md
└── .gitignore
```

---

## 🛠️ Local Development Setup

### 1. Backend (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   The API will be available at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

### 2. Frontend (Next.js)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Copy the example environment file:
   ```bash
   cp .env.example .env.local
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## 🔐 Environment Variables

| Variable | Location | Description | Example |
| :--- | :--- | :--- | :--- |
| `CORS_ORIGINS` | Backend | Comma-separated list of allowed frontend origins. (Defaults to `*` if omitted) | `https://your-frontend.vercel.app,http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Frontend | Base URL of the backend API (without trailing slash). | `https://your-backend.vercel.app` |

---

## 🚀 Vercel Deployment Guide

Deploy this repository as **two separate projects** in the Vercel Dashboard from the same GitHub repository:

### Step 1: Deploy the Backend Project

1. In the Vercel Dashboard, click **Add New... > Project** and import this repository.
2. Configure Project Settings:
   - **Project Name:** `personalized-ai-summarizer-backend` (or your choice).
   - **Framework Preset:** `Other`.
   - **Root Directory:** Click Edit and select `backend`.
3. Environment Variables:
   - Add `CORS_ORIGINS`: leave blank initially or set to your frontend URL once created.
4. Click **Deploy**.
5. Once deployment completes, copy your backend URL (e.g., `https://personalized-ai-summarizer-backend.vercel.app`).
6. Verify deployment by visiting `https://<backend-url>/api/health` in your browser.

### Step 2: Deploy the Frontend Project

1. In the Vercel Dashboard, click **Add New... > Project** and select the same repository again.
2. Configure Project Settings:
   - **Project Name:** `personalized-ai-summarizer-frontend`.
   - **Framework Preset:** `Next.js`.
   - **Root Directory:** Click Edit and select `frontend`.
3. Environment Variables:
   - Add `NEXT_PUBLIC_API_URL`: Paste the backend URL from Step 1 (e.g., `https://personalized-ai-summarizer-backend.vercel.app`).
4. Click **Deploy**.

*(Optional)* Go back to your backend project settings on Vercel and set `CORS_ORIGINS` to your frontend production URL to restrict API access.

---

## 🧪 Testing

To run the backend test suite:
```bash
cd backend
PYTHONPATH=. pytest -v tests/test_api.py
```

To run the frontend production build:
```bash
cd frontend
npm run build
```

---

## ⚠️ Known Scraper Limitations

The built-in scraper parses e-commerce pages using JSON-LD, Microdata, Amazon/Flipkart layouts, and generic HTML heuristics. However:
- E-commerce websites employing aggressive anti-bot challenges (Cloudflare Turnstile, CAPTCHA, Incapsula) or client-side-only rendering may block serverless requests.
- When an external URL cannot be scraped or is protected, the user is provided a clean error notification, and can use the sample dataset or input another valid review page.

