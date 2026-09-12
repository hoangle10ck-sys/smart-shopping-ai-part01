export interface HistoryItem {
  session_id: string;
  raw_query: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  created_at: string;
  completed_at: string | null;
  recommendation_count: number;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
}
