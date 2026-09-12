export interface ScoreBreakdown {
  budget_score: number;
  requirement_score: number;
  purpose_score: number;
  rating_score: number;
  review_score: number;
  source_score: number;
  final_score: number;
}


export interface RecommendationItem {
  product_id: number;
  rank: number;

  name: string;

  category?: string | null;
  brand?: string | null;
  model?: string | null;

  image_url?: string | null;

  price?: number | null;
  currency: string;

  merchant?: string | null;
  product_url?: string | null;
  availability?: string | null;

  rating?: number | null;
  review_count?: number | null;

  specifications: Record<
    string,
    string
  >;

  score: ScoreBreakdown;

  confidence?: number | null;

  evidence?: unknown;
  explanation?: unknown;
}


export interface RequirementItem {
  name: string;
  value: string;
  priority?: number;
}


export interface ParsedRequirement {
  category?: string | null;

  budget_min?: number | null;
  budget_max?: number | null;

  currency?: string;

  purpose?: string[];

  brands?: string[];

  requirements?: RequirementItem[];

  excluded_requirements?: string[];

  sort_preference?: string | null;

  confidence?: number | null;
}


export interface AnalyzeResponse {
  session_id: string;

  requirement?: ParsedRequirement;

  needs_clarification: boolean;

  missing_fields?: string[];

  clarification_question?: string | null;

  search_queries?: string[];

  [key: string]: unknown;
}


export interface SearchPipelineResponse {
  session_id: string;

  recommendations: RecommendationItem[];

  total_recommended: number;

  total_found: number;

  total_filtered: number;

  processing_time_ms: number;

  [key: string]: unknown;
}


export interface ProductOffer {
  id: number;

  merchant?: string | null;

  price?: number | null;

  currency: string;

  availability?: string | null;

  source_id?: number | null;

  source_domain?: string | null;

  source_title?: string | null;

  source_reliability_score?:
    | number
    | null;

  product_url?: string | null;

  last_checked_at: string;
}


export interface ProductDetail {
  id: number;

  name?: string | null;

  category?: string | null;

  brand?: string | null;

  model?: string | null;

  normalized_name?: string | null;

  image_url?: string | null;

  rating?: number | null;

  review_count?: number | null;

  specifications: Record<
    string,
    unknown
  >;

  pros: string[];

  cons: string[];

  offers: ProductOffer[];

  created_at: string;

  updated_at: string;
}


export interface ComparisonOffer {
  merchant?: string | null;

  price?: number | null;

  currency?: string | null;

  availability?: string | null;

  product_url?: string | null;
}


export interface ComparisonProduct {
  product_id: number;

  name?: string | null;

  category?: string | null;

  brand?: string | null;

  model?: string | null;

  image_url?: string | null;

  rating?: number | null;

  review_count?: number | null;

  specifications: Record<
    string,
    unknown
  >;

  pros: string[];

  cons: string[];

  ai_score?: number | null;

  confidence?: number | null;

  recommendation_rank?:
    | number
    | null;

  best_offer?:
    | ComparisonOffer
    | null;
}


export interface ComparisonResult {
  winner_product_id: number;

  summary: string;

  criteria: string[];

  products: ComparisonProduct[];
}


export interface ComparisonResponse {
  id: number;

  session_id: string;

  product_ids: number[];

  result?:
    | ComparisonResult
    | null;

  created_at: string;
}


export interface FeedbackCreateInput {
  session_id: string;

  product_id?: number | null;

  is_helpful: boolean;

  reason?: string | null;

  comment?: string | null;
}


export interface FeedbackResponse {
  id: number;

  session_id: string;

  product_id?: number | null;

  is_helpful: boolean;

  reason?: string | null;

  comment?: string | null;

  created_at: string;
}