"""Ranking metrics from supplied judgments; never infer missing ground truth."""
import math


def ranking_metrics(observations: list[dict], judgments: dict[tuple[str, str], int],
                    catalog_ids: set[str], k: int = 5) -> dict:
    if k < 1:
        raise ValueError("k must be positive")
    rows, incomplete, no_relevant = [], [], []
    for observation in observations:
        if observation["split"] != "evaluation":
            continue
        query_id = observation["id"]
        grades = {asin: judgments[(query_id, asin)] for asin in catalog_ids if (query_id, asin) in judgments}
        if len(grades) != len(catalog_ids) or not catalog_ids:
            incomplete.append(query_id)
            continue
        if any(type(grade) is not int or not 0 <= grade <= 3 for grade in grades.values()):
            raise ValueError("Relevance must be an integer 0..3")
        ranked = observation["parent_asins"][:k]
        if len(set(ranked)) != len(ranked) or not set(ranked) <= catalog_ids:
            raise ValueError("Ranking contains duplicate/unknown identities")
        gains = [grades[asin] for asin in ranked]
        hits = sum(grade >= 2 for grade in gains)
        dcg = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(gains))
        ideal = sorted(grades.values(), reverse=True)[:k]
        idcg = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
        if not idcg:
            no_relevant.append(query_id)
        rows.append(dict(query_id=query_id, precision=hits / k, relevant_returned=hits,
                         ndcg=dcg / idcg if idcg else None))
    ndcgs = [row["ndcg"] for row in rows if row["ndcg"] is not None]
    return dict(k=k, relevance_threshold=2, precision_denominator="k, including unfilled slots",
        precision_at_k=dict(value=sum(r["precision"] for r in rows) / len(rows) if rows else None,
                            numerator=sum(r["relevant_returned"] for r in rows), denominator=k * len(rows),
                            queries=len(rows)),
        ndcg_at_k=dict(value=sum(ndcgs) / len(ndcgs) if ndcgs else None, denominator=len(ndcgs)),
        incomplete_queries=incomplete, zero_ideal_gain_queries=no_relevant, per_query=rows)
