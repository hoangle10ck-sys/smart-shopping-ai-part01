import type { HistoryListResponse } from "@/types/history";

import type {
  AnalyzeResponse,
  ComparisonResponse,
  FeedbackCreateInput,
  FeedbackResponse,
  ProductDetail,
  SearchPipelineResponse,
} from "@/types/shopping";


export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function searchErrorMessage(error: unknown): string {
  return error instanceof ApiError && error.status >= 400 && error.status < 500
    ? error.message
    : "Chưa thể kết nối để tìm kiếm. Vui lòng thử lại sau ít phút.";
}


async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response =
    await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...options,

        headers: {
          "Content-Type":
            "application/json",

          ...(options?.headers ??
            {}),
        },

        cache: "no-store",
      },
    );


  if (!response.ok) {
    let message =
      `API error ${response.status}`;

    try {
      const body =
        await response.json();

      if (
        typeof body?.detail ===
        "string"
      ) {
        message =
          body.detail;
      } else if (
        Array.isArray(
          body?.detail,
        )
      ) {
        message =
          body.detail
            .map(
              (
                item: {
                  msg?: string;
                },
              ) =>
                item.msg ??
                "Validation error",
            )
            .join(", ");
      } else if (
        body?.message
      ) {
        message =
          String(
            body.message,
          );
      }
    } catch {
      // Không parse được JSON.
    }


    throw new ApiError(message, response.status);
  }


  return response.json() as Promise<T>;
}


export function analyzeRequirement(
  rawQuery: string,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(
    "/api/requirements/analyze",
    {
      method: "POST",

      body: JSON.stringify({
        raw_query: rawQuery,
      }),
    },
  );
}

export function researchSearch(rawQuery: string): Promise<SearchPipelineResponse> {
  return request<SearchPipelineResponse>("/api/research/search", { method: "POST", body: JSON.stringify({ raw_query: rawQuery }) });
}

export async function repeatResearchSearch(sessionId: string): Promise<SearchPipelineResponse> {
  const previous = await request<{ raw_query: string; result: SearchPipelineResponse }>(`/api/history/${encodeURIComponent(sessionId)}`);
  if (previous.result?.data_mode !== "research") throw new Error("Phiên không thuộc Research.");
  return request<SearchPipelineResponse>("/api/research/search", { method: "POST", body: JSON.stringify({
    raw_query: previous.raw_query, requirement: previous.result.requirement,
  }) });
}

export function researchStatus(): Promise<{ products: number; default_mode: "demo" | "live" }> {
  return request("/api/research/status");
}


export function clarifyRequirement(
  sessionId: string,
  answer: string,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(
    "/api/requirements/clarify",
    {
      method: "POST",

      body: JSON.stringify({
        session_id: sessionId,
        answer,
      }),
    },
  );
}


export function executeSearch(
  sessionId: string,
  options?: { directUrls?: string[]; sourcePlatforms?: ("shopee" | "lazada")[]; refresh?: boolean },
): Promise<SearchPipelineResponse> {
  return request<SearchPipelineResponse>(
    "/api/search",
    {
      method: "POST",

      body: JSON.stringify({
        session_id: sessionId,
        direct_urls: options?.directUrls ?? [],
        source_platforms: options?.sourcePlatforms ?? ["shopee", "lazada"],
        refresh: options?.refresh ?? false,
      }),
    },
  );
}


export function getSearchResult(
  sessionId: string,
): Promise<SearchPipelineResponse> {
  return request<SearchPipelineResponse>(
    `/api/search/${sessionId}`,
  );
}


export function getProduct(
  productId: number,
  sessionId?: string | null,
): Promise<ProductDetail> {
  return request<ProductDetail>(
    `/api/products/${productId}${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
  );
}


export function createComparison(
  sessionId: string,
  productIds: number[],
): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(
    "/api/comparisons",
    {
      method: "POST",

      body: JSON.stringify({
        session_id: sessionId,

        product_ids:
          productIds,
      }),
    },
  );
}


export function getComparison(
  comparisonId: number,
): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(
    `/api/comparisons/${comparisonId}`,
  );
}


export function createFeedback(
  payload: FeedbackCreateInput,
): Promise<FeedbackResponse> {
  return request<FeedbackResponse>(
    "/api/feedback",
    {
      method: "POST",

      body:
        JSON.stringify(
          payload,
        ),
    },
  );
}

export function getHistory(signal?: AbortSignal): Promise<HistoryListResponse> {
  return request<HistoryListResponse>("/api/history?limit=50", { signal });
}
