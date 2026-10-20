from app.api.routes.comparison import _build_result


def product(product_id, model, variant_id, price):
    return {"product_id":product_id, "name":f"P{product_id}", "model":model,
        "variant_id":variant_id, "specifications":{}, "ai_score":80-product_id,
        "price_type":"CONCRETE",
        "best_offer":{"price":price, "currency":"VND"}, "alternate_offers":[]}


def test_prices_are_comparable_only_for_same_model_and_variant():
    comparable = _build_result(products=[product(1,"X",9,100), product(2,"X",9,120)])
    assert comparable["price_comparability"] == "COMPARABLE"
    mismatched = _build_result(products=[product(1,"X",9,100), product(2,"X",10,80)])
    assert mismatched["price_comparability"] == "NOT_COMPARABLE"
    assert "NOT_COMPARABLE" in mismatched["warnings"][0]


def test_unknown_variant_is_never_price_comparable():
    result = _build_result(products=[product(1,"X",None,100), product(2,"X",None,100)])
    assert result["price_comparability"] == "NOT_COMPARABLE"


def test_different_price_semantics_are_not_comparable():
    left = product(1, "X", 9, 100)
    right = product(2, "X", 9, 100)
    right["price_type"] = None
    assert _build_result(products=[left, right])["price_comparability"] == "NOT_COMPARABLE"
