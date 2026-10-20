export interface ScoreBreakdown {
  budget_score: number;
  requirement_score: number;
  purpose_score: number;
  rating_score: number;
  review_score: number;
  source_score: number;
  final_score: number;
}


export interface RequirementMatch {
  name: string;
  requested_value: string;
  product_value: string | null;
  status: "matched" | "unmet" | "unknown";
  reason: string;
}

export interface FieldEvidence {
  field: string;
  value: string | number;
  source?: string | null;
  domain?: string | null;
  merchant?: string | null;
  url?: string | null;
  retrieved_at?: string | null;
  reliability?: number | null;
}

export interface RecommendationEvidence {
  fields?: FieldEvidence[];
  supporting_evidence?: string[];
  warnings?: string[];
}

export interface ResearchMetadata {
  source_mode?: "HISTORICAL_RESEARCH" | null;
  historical_price?: { amount: string; currency: string; reference_year: number; price_observed_at: null } | null;
  research_provenance?: { dataset_id: string; revision: string; parent_asin: string; dataset_url: string; imported_at: string } | null;
}

export interface RecommendationItem extends ResearchMetadata {
  variant_id?: number | null;
  offer_id?: number | null;
  platform?: string | null;
  freshness_status?: string | null;
  score_version?: string;
  product_suitability?: Record<string, unknown> | null;
  offer_quality?: Record<string, unknown> | null;
  price_type?: "CONCRETE" | null;
  alternate_offers?: Record<string, unknown>[];
  variant?: Record<string, string>;
  product_page_valid?: boolean | null;
  source_observation_valid?: boolean | null;
  verification_level?: "VERIFIED_PUBLIC_API" | "VERIFIED_CONTENT" | "VERIFIED_SEARCH_METADATA" | "UNVERIFIED" | "REJECTED" | null;
  image_source?: string | null;
  evidence_url?: string | null;
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
  last_checked_at?: string | null;

  rating?: number | null;
  review_count?: number | null;

  specifications: Record<
    string,
    string
  >;

  score: ScoreBreakdown;

  confidence?: number | null;

  evidence?: RecommendationEvidence | null;
  requirement_matches?: RequirementMatch[];
  explanation?: unknown;
  pros?: string[];
  cons?: string[];
}


export interface RequirementItem {
  name: string;
  value: string;
  priority?: number;
}


export interface ParsedRequirement {
  budget_mode?: "HARD_MAX" | "FLEXIBLE_TARGET" | "RANGE";
  budget_target?: number | null;
  preferred_min?: number | null;
  preferred_max?: number | null;
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
  requirement?: ParsedRequirement | null;
  status?: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | null;
  data_mode?: "demo" | "live" | "research" | null;
  demo_mode?: boolean;
  data_semantics?: "snapshot" | "legacy_recomputed" | "not_generated";
  warnings?: string[];

  recommendations: RecommendationItem[];

  total_recommended: number;

  total_found: number;

  total_filtered: number;

  processing_time_ms: number;

  [key: string]: unknown;
}


export interface ProductOffer {
  product_page_valid?: boolean | null;
  source_observation_valid?: boolean | null;
  image_url?: string | null;
  image_source?: string | null;
  evidence_url?: string | null;
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


export interface ProductDetail extends ResearchMetadata {
  recommendation?: RecommendationItem | null;
  recommendation_session_id?: string | null;
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


export interface ComparisonProduct extends ResearchMetadata {
  requirement_matches?: RequirementMatch[];
  product_id: number;
  variant_id?: number | null;
  offer_id?: number | null;
  platform?: string | null;
  freshness_status?: string | null;
  product_suitability?: Record<string, unknown> | null;
  offer_quality?: Record<string, unknown> | null;
  alternate_offers?: Record<string, unknown>[];

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
  product_comparison?: Record<string, unknown>[];
  offer_comparison?: Record<string, unknown>[];
  price_comparability?: "COMPARABLE" | "NOT_COMPARABLE";
  warnings?: string[];
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
