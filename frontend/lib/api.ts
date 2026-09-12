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


    throw new Error(message);
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
): Promise<SearchPipelineResponse> {
  return request<SearchPipelineResponse>(
    "/api/search",
    {
      method: "POST",

      body: JSON.stringify({
        session_id: sessionId,
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
): Promise<ProductDetail> {
  return request<ProductDetail>(
    `/api/products/${productId}`,
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