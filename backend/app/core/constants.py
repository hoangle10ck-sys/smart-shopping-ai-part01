"""Central business constants for Smart Shopping AI."""

OFFICIAL_BRAND_DOMAINS: set[str] = {
    "apple.com",
    "samsung.com",
    "sony.com",
    "asus.com",
    "acer.com",
    "dell.com",
    "lenovo.com",
    "hp.com",
    "logitech.com",
    "jbl.com",
}

TRUSTED_RETAILER_DOMAINS: set[str] = {
    "thegioididong.com",
    "fptshop.com.vn",
    "cellphones.com.vn",
    "phongvu.vn",
}

MARKETPLACE_DOMAINS: set[str] = {
    "shopee.vn",
    "lazada.vn",
    "tiki.vn",
}

REVIEW_DOMAINS: set[str] = {
    "gsmarena.com",
    "tomshardware.com",
    "rtings.com",
}

SOURCE_SCORE_OFFICIAL = 100.0

SOURCE_SCORE_TRUSTED_RETAILER = 90.0

SOURCE_SCORE_MARKETPLACE = 80.0

SOURCE_SCORE_REVIEW = 70.0

SOURCE_SCORE_UNKNOWN = 50.0