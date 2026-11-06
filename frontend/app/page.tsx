"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  AnalyzeResponse,
  AVAILABLE_ASPECTS,
  AspectType,
  ReviewRecord,
} from "../lib/types";
import { fetchAnalysis, exportReviewsToCSV } from "../lib/api";

export default function Home() {
  // Input states
  const [productUrl, setProductUrl] = useState("");
  const [selectedAspects, setSelectedAspects] = useState<string[]>([
    "Battery",
    "Camera",
  ]);
  const [preferenceText, setPreferenceText] = useState("");
  const [reviewPoints, setReviewPoints] = useState<number>(4);

  // Status states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyzeResponse | null>(null);

  // Review Explorer filters
  const [filterAspect, setFilterAspect] = useState<string>("All");
  const [filterSentiment, setFilterSentiment] = useState<string>("All");

  // Load sample dataset on initial load
  useEffect(() => {
    handleAnalyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleAspect = (aspect: string) => {
    setSelectedAspects((prev) =>
      prev.includes(aspect)
        ? prev.filter((a) => a !== aspect)
        : [...prev, aspect]
    );
  };

  const handleAnalyze = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);

    try {
      const response = await fetchAnalysis({
        product_url: productUrl.trim() || undefined,
        aspects: selectedAspects,
        preference: preferenceText.trim(),
        review_points: reviewPoints,
      });
      setData(response);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred while communicating with the API.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Filtered reviews for the Explorer table
  const filteredReviews = useMemo(() => {
    if (!data) return [];
    return data.reviews.filter((r) => {
      const matchAspect =
        filterAspect === "All" || r.aspects.includes(filterAspect);
      const matchSent =
        filterSentiment === "All" || r.sentiment === filterSentiment;
      return matchAspect && matchSent;
    });
  }, [data, filterAspect, filterSentiment]);

  // Sentiment bar calculations
  const sentimentPercentages = useMemo(() => {
    if (!data || data.total_reviews === 0) {
      return { pos: 0, neu: 0, neg: 0 };
    }
    const total = data.total_reviews;
    return {
      pos: Math.round((data.sentiment_counts.positive / total) * 100),
      neu: Math.round((data.sentiment_counts.neutral / total) * 100),
      neg: Math.round((data.sentiment_counts.negative / total) * 100),
    };
  }, [data]);

  return (
    <main className="container">
      {/* Header */}
      <header className="header">
        <h1>🛍️ Personalized Product Review Summarizer</h1>
        <p>
          Configure the aspects you care about and inspect review feedback
          tailored to your personal priorities.
        </p>
      </header>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Sidebar / Controls */}
        <aside>
          <div className="card">
            <h2 className="card-title">Analysis Settings</h2>

            {/* Product URL Input */}
            <div className="form-group">
              <label className="form-label" htmlFor="product-url">
                Product Webpage URL
              </label>
              <input
                id="product-url"
                type="url"
                className="form-input"
                placeholder="Leave blank to use bundled dataset"
                value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)}
              />
              <p className="form-helper">
                Paste an Amazon, Flipkart, or e-commerce URL. Leave empty to analyse the 100 sample reviews.
              </p>
            </div>

            {/* Aspects Selector */}
            <div className="form-group">
              <label className="form-label">Important Aspects</label>
              <div className="aspect-chips">
                {AVAILABLE_ASPECTS.map((aspect) => {
                  const isSelected = selectedAspects.includes(aspect);
                  return (
                    <button
                      key={aspect}
                      type="button"
                      className={`chip ${isSelected ? "active" : ""}`}
                      onClick={() => toggleAspect(aspect)}
                    >
                      {isSelected ? "✓ " : "+ "}
                      {aspect}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Preference Text */}
            <div className="form-group">
              <label className="form-label" htmlFor="custom-pref">
                Custom Priorities (optional)
              </label>
              <textarea
                id="custom-pref"
                className="form-textarea"
                rows={3}
                placeholder="Example: I take lots of photos in low light and need fast charging."
                value={preferenceText}
                onChange={(e) => setPreferenceText(e.target.value)}
              />
            </div>

            {/* Review Points Slider */}
            <div className="form-group">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <label className="form-label" htmlFor="review-points">
                  Points per section
                </label>
                <span
                  style={{
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    color: "var(--primary)",
                  }}
                >
                  {reviewPoints}
                </span>
              </div>
              <input
                id="review-points"
                type="range"
                min={2}
                max={8}
                value={reviewPoints}
                onChange={(e) => setReviewPoints(Number(e.target.value))}
                style={{ width: "100%", marginTop: "0.3rem" }}
              />
            </div>

            {/* Submit Button */}
            <button
              className="btn-primary"
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Analysing Reviews...
                </>
              ) : (
                "Analyse Reviews"
              )}
            </button>
          </div>
        </aside>

        {/* Content Area */}
        <section>
          {error && (
            <div className="alert alert-error">
              <strong>Error:</strong> {error}
            </div>
          )}

          {data && (
            <>
              {/* Data source indicator */}
              <div
                style={{
                  marginBottom: "1rem",
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>
                  Source:{" "}
                  <strong>
                    {data.data_source === "bundled_csv"
                      ? "Bundled Sample Dataset (100 synthetic reviews)"
                      : "Scraped Web Page"}
                  </strong>
                </span>
                <button
                  className="btn-secondary"
                  onClick={() => exportReviewsToCSV(filteredReviews)}
                >
                  📥 Export CSV ({filteredReviews.length})
                </button>
              </div>

              {/* Metrics Row */}
              <div className="metrics-row">
                <div className="metric-card">
                  <div className="metric-label">Total Reviews</div>
                  <div className="metric-value">{data.total_reviews}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Average Rating</div>
                  <div className="metric-value">
                    ★ {data.average_rating.toFixed(1)}/5
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Positive Reviews</div>
                  <div
                    className="metric-value"
                    style={{ color: "var(--success-text)" }}
                  >
                    {data.sentiment_counts.positive}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Negative Reviews</div>
                  <div
                    className="metric-value"
                    style={{ color: "var(--danger-text)" }}
                  >
                    {data.sentiment_counts.negative}
                  </div>
                </div>
              </div>

              {/* Informational Message */}
              {data.info_message && (
                <div className="alert alert-info">{data.info_message}</div>
              )}

              {/* Personalized Summary Highlights */}
              <div className="highlights-grid">
                <div className="highlight-box positive">
                  <h3>👍 Customers Like</h3>
                  {data.positive_highlights.length > 0 ? (
                    <ul className="highlight-list">
                      {data.positive_highlights.map((item, idx) => (
                        <li key={idx} className="highlight-item">
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      No matching positive points found for the selected aspects.
                    </p>
                  )}
                </div>

                <div className="highlight-box negative">
                  <h3>⚠️ Customer Concerns</h3>
                  {data.negative_highlights.length > 0 ? (
                    <ul className="highlight-list">
                      {data.negative_highlights.map((item, idx) => (
                        <li key={idx} className="highlight-item">
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      No matching negative points found for the selected aspects.
                    </p>
                  )}
                </div>
              </div>

              {/* Sentiment Overview Bar */}
              <div className="sentiment-bar-container">
                <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
                  Sentiment Overview
                </h3>
                <div className="sentiment-bar">
                  <div
                    className="bar-segment bar-pos"
                    style={{ width: `${sentimentPercentages.pos}%` }}
                    title={`Positive: ${data.sentiment_counts.positive}`}
                  >
                    {sentimentPercentages.pos > 8 ? `${sentimentPercentages.pos}%` : ""}
                  </div>
                  <div
                    className="bar-segment bar-neu"
                    style={{ width: `${sentimentPercentages.neu}%` }}
                    title={`Neutral: ${data.sentiment_counts.neutral}`}
                  >
                    {sentimentPercentages.neu > 8 ? `${sentimentPercentages.neu}%` : ""}
                  </div>
                  <div
                    className="bar-segment bar-neg"
                    style={{ width: `${sentimentPercentages.neg}%` }}
                    title={`Negative: ${data.sentiment_counts.negative}`}
                  >
                    {sentimentPercentages.neg > 8 ? `${sentimentPercentages.neg}%` : ""}
                  </div>
                </div>

                <div className="sentiment-legend">
                  <div className="legend-item">
                    <span
                      className="legend-dot"
                      style={{ background: "#22c55e" }}
                    />
                    <span>
                      Positive: <strong>{data.sentiment_counts.positive}</strong>
                    </span>
                  </div>
                  <div className="legend-item">
                    <span
                      className="legend-dot"
                      style={{ background: "#94a3b8" }}
                    />
                    <span>
                      Neutral: <strong>{data.sentiment_counts.neutral}</strong>
                    </span>
                  </div>
                  <div className="legend-item">
                    <span
                      className="legend-dot"
                      style={{ background: "#ef4444" }}
                    />
                    <span>
                      Negative: <strong>{data.sentiment_counts.negative}</strong>
                    </span>
                  </div>
                </div>
              </div>

              {/* Review Explorer */}
              <div className="card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "1rem",
                    marginBottom: "1rem",
                  }}
                >
                  <h3 className="card-title" style={{ margin: 0 }}>
                    Explore Reviews ({filteredReviews.length})
                  </h3>

                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <div>
                      <select
                        aria-label="Aspect Filter"
                        className="form-select"
                        value={filterAspect}
                        onChange={(e) => setFilterAspect(e.target.value)}
                        style={{ fontSize: "0.85rem", padding: "0.4rem 0.6rem" }}
                      >
                        <option value="All">All Aspects</option>
                        {AVAILABLE_ASPECTS.map((asp) => (
                          <option key={asp} value={asp}>
                            {asp}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <select
                        aria-label="Sentiment Filter"
                        className="form-select"
                        value={filterSentiment}
                        onChange={(e) => setFilterSentiment(e.target.value)}
                        style={{ fontSize: "0.85rem", padding: "0.4rem 0.6rem" }}
                      >
                        <option value="All">All Sentiments</option>
                        <option value="Positive">Positive</option>
                        <option value="Neutral">Neutral</option>
                        <option value="Negative">Negative</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div className="table-container">
                  {filteredReviews.length === 0 ? (
                    <p
                      style={{
                        padding: "2rem 1rem",
                        textAlign: "center",
                        color: "var(--text-muted)",
                      }}
                    >
                      No reviews match the selected filter criteria.
                    </p>
                  ) : (
                    <table className="review-table">
                      <thead>
                        <tr>
                          <th style={{ width: "55%" }}>Review Text</th>
                          <th style={{ width: "10%" }}>Rating</th>
                          <th style={{ width: "15%" }}>Sentiment</th>
                          <th style={{ width: "20%" }}>Aspects</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredReviews.map((rev, i) => (
                          <tr key={i}>
                            <td>{rev.review_text}</td>
                            <td>★ {rev.rating}</td>
                            <td>
                              <span
                                className={`badge badge-${rev.sentiment.toLowerCase()}`}
                              >
                                {rev.sentiment}
                              </span>
                            </td>
                            <td>
                              {rev.aspects.length > 0 ? (
                                rev.aspects.map((asp) => (
                                  <span key={asp} className="aspect-tag">
                                    {asp}
                                  </span>
                                ))
                              ) : (
                                <span
                                  style={{
                                    color: "var(--text-muted)",
                                    fontSize: "0.75rem",
                                  }}
                                >
                                  None
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>

              {/* Attribution / Technical note */}
              <p
                style={{
                  marginTop: "1.5rem",
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                  textAlign: "center",
                }}
              >
                Summarization is powered by VADER sentiment analysis, keyword aspect
                tagging, and TF-IDF cosine relevance ranking. The bundled dataset
                consists of 100 synthetic sample reviews.
              </p>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

