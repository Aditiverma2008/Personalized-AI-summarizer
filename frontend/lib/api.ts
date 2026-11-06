import { AnalyzeRequest, AnalyzeResponse } from "./types";

export function getApiBaseUrl(): string {
  // If NEXT_PUBLIC_API_URL is configured, use it
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
}

export async function fetchAnalysis(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/api/analyze`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const errorMsg = data?.detail || `API request failed with status ${res.status}`;
    throw new Error(errorMsg);
  }

  return data as AnalyzeResponse;
}

export function exportReviewsToCSV(reviews: AnalyzeResponse["reviews"], filename = "analysed_reviews.csv"): void {
  const headers = ["product_id", "review_text", "rating", "sentiment", "sentiment_score", "aspects"];
  
  const csvRows = [
    headers.join(","),
    ...reviews.map((r) => {
      const escapedText = `"${r.review_text.replace(/"/g, '""')}"`;
      const escapedAspects = `"${r.aspects.join("; ")}"`;
      return [
        r.product_id,
        escapedText,
        r.rating,
        r.sentiment,
        r.sentiment_score,
        escapedAspects,
      ].join(",");
    }),
  ];

  const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

