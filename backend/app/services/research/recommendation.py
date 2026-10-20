"""Research adapter: existing matcher/snapshot, no merchant offers or network."""
from __future__ import annotations

import re
from decimal import Decimal
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ResearchProduct, HistoricalPriceReference, Recommendation, RecommendationSnapshot
from app.schemas.evidence import EvidenceReport, EvidenceBreakdown, FieldEvidence, RecommendationExplanation
from app.schemas.ranking import ScoringCandidate, ScoreBreakdown, FilterDecision
from app.schemas.recommendation import RecommendationItem
from app.schemas.requirement import RequirementData, RequirementItem
from app.services.filter.hard_filter import HardFilterService, normalized
from app.services.recommendation.recommendation_service import RecommendationRunResult
from app.services.scoring.scoring_engine import ScoringEngine
from app.services.normalization.text_normalizer import remove_diacritics
from app.schemas.evidence import RequirementMatch

WARNING = "Dữ liệu nghiên cứu (2023) — không phải giá bán hiện tại. Không có offer, tồn kho hoặc SKU đã xác minh."
DATASET_PAGE = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"


def _budget(text: str) -> dict:
    """Clause-local money grammar; never borrow a comparator from a RAM clause."""
    unit = r"usd|dollars?|trieu|vnd"
    currencies = {"USD" if u in {"usd", "dollar", "dollars"} else "VND"
                  for u in re.findall(rf"\b({unit})\b", text)}
    if len(currencies) > 1:
        raise ValueError("Hãy dùng một loại tiền tệ cho ngân sách; Research không tự quy đổi USD/VND.")
    currency = next(iter(currencies), "VND")
    span = re.search(rf"\b(?:tu|from|between)\s+(\d+)\s*({unit})?\s*(?:den|to|and|-)\s*(\d+)\s*({unit})\b", text)
    if span:
        low_unit, high_unit = span[2] or span[4], span[4]
        lower = int(span[1]) * (1000000 if low_unit == "trieu" else 1)
        upper = int(span[3]) * (1000000 if high_unit == "trieu" else 1)
        if lower > upper:
            raise ValueError("Ngân sách tối thiểu không được lớn hơn ngân sách tối đa.")
        return dict(budget_min=lower, budget_max=upper, currency=currency)
    money = list(re.finditer(rf"\b(?:(toi thieu|it nhat|at least|tu|from|toi da|khong qua|at most|duoi|under|up to)\s+)?(\d+)\s*({unit})\b", text))
    if len(money) > 1:
        raise ValueError("Hãy viết khoảng ngân sách theo dạng từ 20 đến 50 USD.")
    if not money:
        return dict(currency=currency)
    found = money[0]
    amount = int(found[2]) * (1000000 if found[3] == "trieu" else 1)
    minimum = found[1] in {"toi thieu", "it nhat", "at least", "tu", "from"}
    return dict(budget_min=amount if minimum else None, budget_max=None if minimum else amount, currency=currency)


def parse_query(query: str) -> RequirementData:
    """Transparent local Vietnamese/English grammar; unsupported input stays unknown."""
    text = normalized(query)
    numeric_text = remove_diacritics(query).lower()
    if re.search(r"\d+[.,]\d+\s*(usd|dollars?|trieu|vnd)\b", numeric_text):
        raise ValueError("MVP Research nhận ngân sách số nguyên USD/VND; không tự làm tròn giá trị thập phân.")
    category = None
    for aliases, value in [(("phu kien dien thoai", "op lung", "phone case", "phone accessories"), "phu kien dien thoai"),
                           (("phu kien dien tu", "electronic accessories"), "phu kien dien tu"),
                           (("dien thoai", "smartphone", "cell phone"), "dien thoai"),
                           (("tai nghe", "headphone", "earbud"), "tai nghe"),
                           (("laptop", "may tinh xach tay"), "laptop"),
                           (("man hinh", "monitor"), "man hinh"),
                           (("ban phim", "keyboard"), "ban phim"),
                           (("chuot", "mouse"), "chuot"), (("dien tu", "electronics"), "dien tu")]:
        if any(alias in text for alias in aliases):
            category = value
            break
    budget = _budget(numeric_text)
    requirements = []
    for aliases, key, unit in [("ram", "ram", "gb|tb"), ("storage|ssd|bo nho", "storage", "gb|tb"), ("camera", "camera", "mp")]:
        found = re.search(rf"\b(?:{aliases})\s*(?:(toi thieu|it nhat|at least|toi da|khong qua|at most|chinh xac|exactly)\s*)?(\d+)\s*({unit})\b", text)
        if found:
            comparator = found[1] or "chinh xac"
            requirements.append(RequirementItem(name=key, value=f"{comparator} {found[2]} {found[3]}", priority=5))
    for phrase, key, value in [("pin lau", "battery", "pin lâu"), ("camera tot", "camera", "tốt")]:
        if phrase in text:
            requirements.append(RequirementItem(name=key, value=value, priority=3))
    for aliases, keyword in [(("bluetooth",), "bluetooth"), (("khong day", "wireless"), "wireless"),
                             (("chong on", "noise cancelling"), "noise cancelling")]:
        if any(alias in text for alias in aliases):
            requirements.append(RequirementItem(name="keyword", value=keyword, priority=3))
    brands, excluded = [], []
    for brand in ("Samsung", "Apple", "Sony", "Lenovo", "Dell", "Asus", "Nokia"):
        if not re.search(rf"\b{brand.lower()}\b", text):
            continue
        negative = re.search(rf"\b(?:khong(?:\s+(?:mua|chon|lay|thich|dung))?|tru|ngoai tru|loai tru|not|without|exclude)\s+{brand.lower()}\b", text)
        (excluded if negative else brands).append(brand)
    purpose = []
    for aliases, label in [(("lap trinh", "programming", "coding"), "lập trình"),
                           (("choi game", "gaming"), "chơi game"),
                           (("hoc tap", "di hoc", "study"), "học tập"),
                           (("van phong", "office"), "văn phòng"),
                           (("do hoa", "graphic design"), "đồ họa")]:
        if any(alias in text for alias in aliases):
            purpose.append(label)
    return RequirementData(category=category, **budget, purpose=purpose,
                           brands=brands, excluded_requirements=excluded,
                           requirements=requirements, confidence=.6 if category else 0)


def provenance(row: ResearchProduct) -> dict:
    return dict(dataset_id=row.dataset_id, revision=row.revision, parent_asin=row.external_product_id,
                source_category=row.source_category, source_url=row.source_url, dataset_url=DATASET_PAGE,
                input_sha256=row.input_sha256, record_sha256=row.record_sha256, line_number=row.line_number,
                imported_at=row.imported_at.isoformat(), identity_scope="parent product group; not SKU",
                source_mode="HISTORICAL_RESEARCH")


def price_view(ref: HistoricalPriceReference | None) -> dict | None:
    if ref is None:
        return None
    return dict(amount=ref.amount, currency=ref.currency, reference_year=ref.reference_year,
                price_observed_at=None, imported_at=ref.imported_at.isoformat(), source=ref.source,
                status="HISTORICAL_PRICE_AVAILABLE")


def catalog_metadata(db: Session, product_id: int) -> dict:
    row = db.scalar(select(ResearchProduct).where(ResearchProduct.product_id == product_id))
    if row is None:
        return {}
    ref = db.scalar(select(HistoricalPriceReference).where(HistoricalPriceReference.research_product_id == row.id))
    return dict(source_mode="HISTORICAL_RESEARCH", research_provenance=provenance(row), historical_price=price_view(ref))


def evaluate(db: Session, requirement: RequirementData, *, revision: str | None = None, top_k: int = 5):
    warnings = [WARNING]
    if requirement.purpose:
        warnings.append("PURPOSE_NOT_SCORED: metadata chưa đủ để chứng minh hiệu năng cho mục đích sử dụng; không cộng điểm suy đoán.")
    if requirement.category is None:
        warnings.append("Chưa nhận diện danh mục; hãy nêu điện thoại, phụ kiện điện thoại, tai nghe, laptop hoặc điện tử.")
        return RecommendationRunResult(requirement, [], [], [], 0, 0, data_mode="research"), warnings
    if revision is None:
        revision = db.scalar(select(ResearchProduct.revision).order_by(ResearchProduct.imported_at.desc(), ResearchProduct.id.desc()).limit(1))
    rows = db.execute(select(Product, ResearchProduct, HistoricalPriceReference)
        .join(ResearchProduct, Product.id == ResearchProduct.product_id)
        .outerjoin(HistoricalPriceReference, ResearchProduct.id == HistoricalPriceReference.research_product_id)
        .where(ResearchProduct.revision == revision)
        .order_by(ResearchProduct.external_product_id).limit(5001)).all()
    if len(rows) > 5000:
        raise ValueError("Research MVP catalog limit exceeded; select a bounded revision")
    has_budget = any(v is not None for v in (requirement.budget_min, requirement.budget_max, requirement.budget_target))
    if has_budget and requirement.currency != "USD":
        warnings.append("BUDGET_NOT_COMPARABLE: không lọc/chấm giá USD theo VND; không tự quy đổi FX.")
    without_budget = requirement.model_copy(update=dict(budget_min=None, budget_max=None, budget_target=None,
        preferred_min=None, preferred_max=None, budget_mode="HARD_MAX"))
    engine = ScoringEngine()
    candidates, decisions, accepted = [], [], []
    for product, research, ref in rows:
        candidate = ScoringCandidate(product_id=product.id, name=product.name, category=product.category,
            brand=product.brand, model=product.model, specifications=product.specifications,
            rating=product.rating, review_count=product.review_count, price=None, currency="USD", source_reliability=0)
        candidates.append(candidate)
        decision = HardFilterService().evaluate(candidate, without_budget)
        matches = engine.requirement_matches(candidate, requirement)
        native_text = normalized(" ".join([product.name, str(research.metadata_fields.get("features") or ""),
                                          str(research.metadata_fields.get("description") or "")]))
        for index, wanted in enumerate(requirement.requirements):
            if wanted.name == "keyword":
                hit = bool(re.search(rf"\b{re.escape(normalized(wanted.value))}\b", native_text))
                matches[index] = RequirementMatch(name="keyword", requested_value=wanted.value,
                    product_value=wanted.value if hit else None, status="matched" if hit else "unknown",
                    reason="Từ khóa có trong metadata; không chứng minh chất lượng/hiệu năng." if hit else "Không có bằng chứng từ khóa trong metadata.")
        reasons = list(decision.reasons)
        if decision.accepted and any(item.priority == 5 and match.status != "matched"
                                     for item, match in zip(requirement.requirements, matches)):
            reasons.append("Không đủ bằng chứng đáp ứng thông số bắt buộc (unknown không là matched).")
        budget_score = None
        if has_budget and requirement.currency == "USD":
            if ref is None or ref.currency != "USD":
                reasons.append("Thiếu giá tham khảo USD để xác minh ngân sách nghiên cứu.")
            else:
                price = Decimal(ref.amount)
                lower, upper = requirement.budget_min, requirement.budget_max
                if requirement.budget_mode != "FLEXIBLE_TARGET" and (
                    (lower is not None and price < lower) or (upper is not None and price > upper)):
                    reasons.append("Giá lịch sử ngoài ngân sách USD (không phải giá hiện tại).")
                else:
                    budget_score = 100.0
        decisions.append(FilterDecision(product_id=product.id, accepted=not reasons,
            rejection_stage=decision.rejection_stage or ("research_constraints" if reasons else None), reasons=reasons))
        if reasons:
            continue
        requirement_score = (sum(r.priority for r, m in zip(requirement.requirements, matches) if m.status == "matched")
                             / sum(r.priority for r in requirement.requirements) * 100) if requirement.requirements else None
        parts = {"requirements": requirement_score,
                 "rating": engine.rating_score(candidate), "reviews": engine.review_score(candidate), "budget": budget_score}
        base_weights = {"requirements": .60, "rating": .25, "reviews": .05, "budget": .10}
        denominator = sum(base_weights[key] for key, value in parts.items() if value is not None)
        weights = {key: base_weights[key] / denominator if value is not None else 0 for key, value in parts.items()}
        final = round(sum((parts[key] or 0) * weight for key, weight in weights.items()), 2)
        score = ScoreBreakdown(budget_score=budget_score or 0, requirement_score=parts["requirements"] or 0,
            purpose_score=0, rating_score=parts["rating"], review_score=parts["reviews"], source_score=0, final_score=final)
        accepted.append((candidate, product, research, ref, matches, score, parts, weights))
    accepted.sort(key=lambda row: (-row[5].final_score, row[2].external_product_id))
    items = []
    for rank, (candidate, product, research, ref, matches, score, parts, weights) in enumerate(accepted[:top_k], 1):
        known = [product.name, product.category, product.brand, product.image_url, product.rating, product.review_count]
        completeness = round(sum(value is not None for value in known) / len(known) * 100, 2)
        fields = [FieldEvidence(field=key, value=value, source=research.dataset_id, url=DATASET_PAGE)
                  for key, value in {"name": product.name, "rating": product.rating, "review_count": product.review_count,
                                     **product.specifications}.items() if value is not None]
        notes = [f"parent_asin={research.external_product_id}; revision={research.revision}; dòng {research.line_number}"]
        if ref:
            fields.append(FieldEvidence(field="historical_price_USD", value=ref.amount, source=research.dataset_id, url=DATASET_PAGE))
        for match in matches:
            if match.name == "keyword" and match.status == "matched":
                fields.append(FieldEvidence(field="metadata_keyword", value=match.product_value,
                                            source=research.dataset_id, url=DATASET_PAGE))
        evidence = EvidenceReport(confidence=completeness, source_count=1, offer_count=0, fields=fields,
            breakdown=EvidenceBreakdown(source_reliability=0, product_completeness=completeness,
                offer_completeness=0, consistency=0, corroboration=0), supporting_evidence=notes, warnings=warnings)
        fit = [f"{m.name}: {m.product_value} ({m.status})" for m in matches if m.status == "matched"]
        tradeoffs = [f"{m.name}: {m.reason}" for m in matches if m.status != "matched"]
        items.append(RecommendationItem(product_id=product.id, rank=rank, name=product.name,
            category=product.category, brand=product.brand, model=product.model, image_url=product.image_url,
            rating=product.rating, review_count=product.review_count, specifications=product.specifications,
            price=None, currency="USD", score=score, confidence=completeness, evidence=evidence,
            requirement_matches=matches, source_mode="HISTORICAL_RESEARCH",
            historical_price=price_view(ref), research_provenance=provenance(research), evidence_url=DATASET_PAGE,
            score_version="research-v1", product_suitability=dict(score=score.final_score, breakdown=parts,
                weights=weights, confidence=completeness, insufficient_evidence=any(m.status == "unknown" for m in matches)),
            offer_quality=None, explanation=RecommendationExplanation(summary=WARNING, why_fit=fit,
                tradeoffs=tradeoffs + ["Không có offer hiện hành; giá và rating chỉ là metadata lịch sử."],
                evidence_notes=notes, generation_mode="fallback")))
    return RecommendationRunResult(requirement, candidates, decisions, items, len(rows), len(accepted), data_mode="research"), warnings


def save_result(db: Session, session_id: str, result: RecommendationRunResult):
    if db.get(RecommendationSnapshot, session_id):
        raise ValueError("Research snapshot already exists; create a new query")
    for item in result.recommendations:
        db.add(Recommendation(session_id=session_id, product_id=item.product_id, rank=item.rank,
            confidence=item.confidence, explanation=item.explanation.model_dump(mode="json"), **item.score.model_dump()))
    db.add(RecommendationSnapshot(session_id=session_id, payload={"version": 1,
        "result": TypeAdapter(RecommendationRunResult).dump_python(result, mode="json")}))
