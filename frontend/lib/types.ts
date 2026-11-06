export interface ReviewRecord {
  product_id: string;
  review_text: string;
  rating: number;
  sentiment_score: number;
  sentiment: "Positive" | "Neutral" | "Negative";
  aspects: string[];
}

export interface SentimentCounts {
  positive: number;
  neutral: number;
  negative: number;
}

export interface AnalyzeResponse {
  total_reviews: number;
  average_rating: number;
  sentiment_counts: SentimentCounts;
  positive_highlights: string[];
  negative_highlights: string[];
  reviews: ReviewRecord[];
  info_message?: string | null;
  data_source: "bundled_csv" | "scraped_url";
}

export interface AnalyzeRequest {
  product_url?: string;
  aspects: string[];
  preference?: string;
  review_points: number;
}

export const AVAILABLE_ASPECTS = [
  "Battery",
  "Camera",
  "Performance",
  "Price",
  "Display",
  "Design & Build",
  "Sound",
  "Ease of Use",
] as const;

export type AspectType = (typeof AVAILABLE_ASPECTS)[number];

