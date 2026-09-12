"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useParams,
  useRouter,
} from "next/navigation";

import {
  SiteHeader,
} from "@/components/site-header";

import {
  getProduct,
} from "@/lib/api";

import type {
  ProductDetail,
  ProductOffer,
} from "@/types/shopping";


/* =========================================================
   HELPERS
========================================================= */

function formatPrice(
  value?: number | null,
  currency = "VND",
) {
  if (value == null) {
    return "Liên hệ";
  }

  if (currency === "VND") {
    return new Intl.NumberFormat(
      "vi-VN",
      {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
      },
    ).format(value);
  }

  return (
    `${value.toLocaleString("vi-VN")} ${currency}`
  );
}


function formatDate(
  value?: string | null,
) {
  if (!value) {
    return "Chưa rõ";
  }

  const date = new Date(
    value
  );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "Chưa rõ";
  }

  return new Intl.DateTimeFormat(
    "vi-VN",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


function merchantName(
  offer?: ProductOffer | null,
) {
  if (!offer) {
    return "Cửa hàng";
  }

  return (
    offer.merchant
    || offer.source_domain
    || "Cửa hàng"
  );
}


function availabilityLabel(
  value?: string | null,
) {
  if (!value) {
    return "Chưa rõ tình trạng";
  }

  const normalized = value
    .trim()
    .toLowerCase()
    .replaceAll("_", " ");

  if (
    [
      "in stock",
      "available",
      "con hang",
      "còn hàng",
    ].includes(normalized)
  ) {
    return "Còn hàng";
  }

  if (
    [
      "out of stock",
      "sold out",
      "unavailable",
      "het hang",
      "hết hàng",
    ].includes(normalized)
  ) {
    return "Hết hàng";
  }

  return value;
}


function availabilityClass(
  value?: string | null,
) {
  const normalized = (
    value
    || ""
  )
    .toLowerCase()
    .replaceAll("_", " ");

  if (
    normalized.includes(
      "out"
    )
    || normalized.includes(
      "sold"
    )
    || normalized.includes(
      "hết"
    )
  ) {
    return (
      "bg-red-50 text-red-700 border-red-200"
    );
  }

  return (
    "bg-emerald-50 text-emerald-700 border-emerald-200"
  );
}


function specIcon(
  key: string,
) {
  const value =
    key.toLowerCase();

  if (
    value.includes("ram")
  ) {
    return "🧠";
  }

  if (
    value.includes("cpu")
    || value.includes("processor")
    || value.includes("chip")
  ) {
    return "⚙️";
  }

  if (
    value.includes("ssd")
    || value.includes("storage")
    || value.includes("disk")
  ) {
    return "💾";
  }

  if (
    value.includes("screen")
    || value.includes("display")
    || value.includes("màn")
  ) {
    return "🖥️";
  }

  if (
    value.includes("battery")
    || value.includes("pin")
  ) {
    return "🔋";
  }

  if (
    value.includes("camera")
  ) {
    return "📷";
  }

  if (
    value.includes("weight")
    || value.includes("trọng")
  ) {
    return "⚖️";
  }

  if (
    value.includes("mic")
  ) {
    return "🎙️";
  }

  if (
    value.includes("bluetooth")
  ) {
    return "📡";
  }

  return "✓";
}


function prettySpecName(
  key: string,
) {
  const map: Record<
    string,
    string
  > = {
    ram: "RAM",
    cpu: "CPU",
    processor: "Bộ xử lý",
    storage: "Bộ nhớ",
    ssd: "Ổ cứng SSD",
    display: "Màn hình",
    screen: "Màn hình",
    battery: "Pin",
    weight: "Trọng lượng",
    camera: "Camera",
    microphone: "Microphone",
    mic: "Microphone",
    bluetooth: "Bluetooth",
  };

  return (
    map[
      key.toLowerCase()
    ]
    || key
      .replaceAll("_", " ")
      .replace(
        /\b\w/g,
        (char) =>
          char.toUpperCase(),
      )
  );
}


/* =========================================================
   PAGE
========================================================= */

export default function ProductPage() {
  const router =
    useRouter();

  const params = useParams<{
    productId: string;
  }>();

  const [
    product,
    setProduct,
  ] = useState<
    ProductDetail
    | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(
    true
  );

  const [
    error,
    setError,
  ] = useState<
    string
    | null
  >(null);

  const [
    imageFailed,
    setImageFailed,
  ] = useState(
    false
  );


  /* =======================================================
     LOAD PRODUCT
  ======================================================= */

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(
          true
        );

        setError(
          null
        );

        const productId =
          Number(
            params.productId
          );

        if (
          !Number.isFinite(
            productId
          )
        ) {
          throw new Error(
            "Mã sản phẩm không hợp lệ.",
          );
        }

        const result =
          await getProduct(
            productId
          );

        if (
          active
        ) {
          setProduct(
            result
          );

          setImageFailed(
            false
          );
        }
      } catch (
        caught
      ) {
        if (
          !active
        ) {
          return;
        }

        setError(
          caught
          instanceof Error
            ? caught.message
            : "Không thể tải sản phẩm.",
        );
      } finally {
        if (
          active
        ) {
          setLoading(
            false
          );
        }
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [
    params.productId,
  ]);


  /* =======================================================
     DERIVED DATA
  ======================================================= */

  const sortedOffers =
    useMemo(
      () => {
        if (
          !product
        ) {
          return [];
        }

        return [
          ...product.offers,
        ].sort(
          (
            first,
            second,
          ) => {
            if (
              first.price
              == null
            ) {
              return 1;
            }

            if (
              second.price
              == null
            ) {
              return -1;
            }

            return (
              first.price
              - second.price
            );
          },
        );
      },
      [
        product,
      ],
    );


  const bestOffer =
    sortedOffers[0]
    || null;


  const specs =
    useMemo(
      () => {
        if (
          !product
        ) {
          return [];
        }

        return Object.entries(
          product
            .specifications
          || {},
        ).filter(
          (
            [
              ,
              value,
            ],
          ) =>
            value
            != null
            && String(
              value
            ).trim()
            !== "",
        );
      },
      [
        product,
      ],
    );


  const hasImage =
    Boolean(
      product?.image_url
      && !imageFailed
    );


  /* =======================================================
     LOADING
  ======================================================= */

  if (
    loading
  ) {
    return (
      <main className="min-h-screen bg-slate-50">
        <SiteHeader />

        <div className="mx-auto flex min-h-[70vh] max-w-7xl items-center justify-center px-5">
          <div className="text-center">
            <div className="mx-auto h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />

            <p className="mt-5 font-bold text-slate-500">
              Đang tải thông tin sản phẩm...
            </p>
          </div>
        </div>
      </main>
    );
  }


  /* =======================================================
     ERROR
  ======================================================= */

  if (
    error
    || !product
  ) {
    return (
      <main className="min-h-screen bg-slate-50">
        <SiteHeader />

        <section className="mx-auto max-w-4xl px-5 py-24">
          <div className="rounded-[32px] border border-red-200 bg-white p-10 text-center shadow-sm">
            <div className="text-5xl">
              ⚠️
            </div>

            <h1 className="mt-5 text-2xl font-black text-slate-950">
              Không thể tải sản phẩm
            </h1>

            <p className="mt-3 text-slate-500">
              {error
                || "Không tìm thấy sản phẩm."}
            </p>

            <button
              type="button"
              onClick={() =>
                router.back()
              }
              className="mt-7 rounded-2xl bg-slate-950 px-6 py-3 font-bold text-white transition hover:bg-blue-600"
            >
              ← Quay lại
            </button>
          </div>
        </section>
      </main>
    );
  }


  /* =======================================================
     UI
  ======================================================= */

  return (
    <main className="min-h-screen bg-slate-50">
      <SiteHeader />


      {/* ===================================================
          BREADCRUMB
      =================================================== */}

      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-4 lg:px-8">
          <button
            type="button"
            onClick={() =>
              router.back()
            }
            className="text-sm font-bold text-slate-500 transition hover:text-blue-600"
          >
            ← Quay lại kết quả tìm kiếm
          </button>
        </div>
      </div>


      {/* ===================================================
          PRODUCT HERO
      =================================================== */}

      <section className="bg-white">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 py-10 lg:grid-cols-[1fr_1.05fr] lg:px-8 lg:py-14">

          {/* IMAGE */}
          <div>
            <div className="sticky top-6 overflow-hidden rounded-[36px] border border-slate-200 bg-gradient-to-br from-white via-slate-50 to-blue-50 shadow-sm">
              <div className="relative flex min-h-[480px] items-center justify-center p-8">

                {hasImage ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={
                      product.image_url!
                    }
                    alt={
                      product.name
                      || "Sản phẩm"
                    }
                    onError={() =>
                      setImageFailed(
                        true
                      )
                    }
                    className="max-h-[430px] w-full object-contain transition duration-500 hover:scale-105"
                  />
                ) : (
                  <div className="text-center">
                    <div className="mx-auto flex h-32 w-32 items-center justify-center rounded-[36px] bg-white text-7xl shadow-sm">
                      🛍️
                    </div>

                    <h3 className="mt-6 text-lg font-black text-slate-700">
                      Chưa có ảnh sản phẩm
                    </h3>

                    <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-slate-400">
                      Nguồn hiện tại chưa cung cấp ảnh.
                      Bạn có thể mở trang cửa hàng để xem thêm.
                    </p>
                  </div>
                )}


                {bestOffer && (
                  <div className="absolute bottom-5 left-5 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-extrabold text-emerald-700">
                    Thông tin offer đã lưu
                  </div>
                )}
              </div>
            </div>
          </div>


          {/* INFORMATION */}
          <div className="flex flex-col justify-center">

            {/* TAG */}
            <div className="flex flex-wrap gap-2">
              {product.brand && (
                <span className="rounded-full bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-wide text-blue-700">
                  {product.brand}
                </span>
              )}

              {product.category && (
                <span className="rounded-full bg-slate-100 px-4 py-2 text-xs font-black uppercase tracking-wide text-slate-600">
                  {product.category}
                </span>
              )}

              {bestOffer && (
                <span
                  className={[
                    "rounded-full border px-4 py-2",
                    "text-xs font-black",
                    availabilityClass(
                      bestOffer.availability
                    ),
                  ].join(" ")}
                >
                  {availabilityLabel(
                    bestOffer.availability
                  )}
                </span>
              )}
            </div>


            {/* NAME */}
            <h1 className="mt-5 text-3xl font-black leading-tight tracking-tight text-slate-950 md:text-4xl lg:text-5xl">
              {product.name
                || "Sản phẩm"}
            </h1>


            {/* MODEL */}
            {product.model && (
              <p className="mt-4 text-sm font-semibold text-slate-500">
                Model:{" "}
                <span className="font-black text-slate-700">
                  {product.model}
                </span>
              </p>
            )}


            {/* RATING */}
            <div className="mt-6 flex flex-wrap items-center gap-3">
              {product.rating != null ? (
                <div className="rounded-2xl bg-amber-50 px-4 py-2.5 font-black text-amber-700">
                  ⭐ {product.rating.toFixed(1)} / 5
                </div>
              ) : (
                <div className="rounded-2xl bg-slate-100 px-4 py-2.5 text-sm font-bold text-slate-500">
                  Chưa có rating
                </div>
              )}

              {product.review_count != null && (
                <div className="rounded-2xl bg-slate-100 px-4 py-2.5 text-sm font-bold text-slate-600">
                  {product.review_count.toLocaleString(
                    "vi-VN"
                  )}{" "}
                  lượt đánh giá
                </div>
              )}

              {sortedOffers.length > 0 && (
                <div className="rounded-2xl bg-blue-50 px-4 py-2.5 text-sm font-bold text-blue-700">
                  🛒 {sortedOffers.length} nơi bán
                </div>
              )}
            </div>


            {/* PRICE BOX */}
            <div className="mt-8 rounded-[30px] border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-indigo-50 p-6 shadow-sm">
              <p className="text-sm font-bold text-slate-500">
                Giá tốt nhất hiện tìm thấy
              </p>

              <p className="mt-2 text-4xl font-black tracking-tight text-blue-600 lg:text-5xl">
                {formatPrice(
                  bestOffer?.price,
                  bestOffer?.currency
                  || "VND",
                )}
              </p>

              {bestOffer && (
                <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-slate-500">
                    Nơi bán:
                  </span>

                  <span className="font-black text-slate-800">
                    {merchantName(
                      bestOffer
                    )}
                  </span>
                </div>
              )}


              {bestOffer?.product_url ? (
                <a
                  href={
                    bestOffer.product_url
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-6 flex w-full items-center justify-center rounded-2xl bg-blue-600 px-6 py-4 text-sm font-black text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700"
                >
                  Xem sản phẩm tại cửa hàng ↗
                </a>
              ) : (
                <button
                  type="button"
                  disabled
                  className="mt-6 w-full cursor-not-allowed rounded-2xl bg-slate-200 px-6 py-4 text-sm font-black text-slate-400"
                >
                  Chưa có link mua hàng
                </button>
              )}


              <p className="mt-4 text-xs leading-5 text-slate-400">
                Giá và tình trạng sản phẩm được lấy từ
                nguồn tìm kiếm và có thể thay đổi theo
                thời điểm.
              </p>
            </div>
          </div>
        </div>
      </section>


      {/* ===================================================
          MAIN CONTENT
      =================================================== */}

      <section className="border-t border-slate-200">
        <div className="mx-auto max-w-7xl space-y-8 px-5 py-10 lg:px-8">


          {/* QUICK INFO */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

            <InfoCard
              icon="🏷️"
              label="Thương hiệu"
              value={
                product.brand
                || "Chưa có dữ liệu"
              }
            />

            <InfoCard
              icon="💻"
              label="Model"
              value={
                product.model
                || "Chưa có dữ liệu"
              }
            />

            <InfoCard
              icon="⭐"
              label="Đánh giá"
              value={
                product.rating != null
                  ? `${product.rating.toFixed(1)}/5`
                  : "Chưa có dữ liệu"
              }
            />

            <InfoCard
              icon="🛒"
              label="Nguồn bán"
              value={
                sortedOffers.length
                  ? `${sortedOffers.length} nguồn`
                  : "Chưa có dữ liệu"
              }
            />
          </div>


          {/* SPECIFICATIONS */}
          <section className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm lg:p-8">

            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-600">
                  Specifications
                </p>

                <h2 className="mt-2 text-2xl font-black text-slate-950">
                  Thông số kỹ thuật
                </h2>
              </div>

              <div className="hidden h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-2xl sm:flex">
                ⚙️
              </div>
            </div>


            {specs.length > 0 ? (
              <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

                {specs.map(
                  (
                    [
                      key,
                      value,
                    ],
                  ) => (
                    <div
                      key={key}
                      className="group flex gap-4 rounded-2xl border border-slate-100 bg-slate-50 p-5 transition hover:border-blue-200 hover:bg-blue-50/50"
                    >
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-xl shadow-sm">
                        {specIcon(
                          key
                        )}
                      </div>

                      <div className="min-w-0">
                        <p className="text-xs font-black uppercase tracking-wide text-slate-400">
                          {prettySpecName(
                            key
                          )}
                        </p>

                        <p className="mt-1 break-words font-black leading-6 text-slate-800">
                          {String(
                            value
                          )}
                        </p>
                      </div>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <EmptyBlock
                icon="📋"
                title="Chưa có thông số chi tiết"
                description="Nguồn tìm kiếm hiện tại chưa cung cấp đủ thông số kỹ thuật của sản phẩm."
              />
            )}
          </section>


          {/* PROS / CONS */}
          <div className="grid gap-6 lg:grid-cols-2">

            {/* PROS */}
            <section className="rounded-[32px] border border-emerald-200 bg-white p-6 shadow-sm lg:p-8">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-2xl">
                  ✓
                </div>

                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-emerald-600">
                    Điểm mạnh
                  </p>

                  <h2 className="text-xl font-black text-slate-950">
                    Ưu điểm
                  </h2>
                </div>
              </div>


              {product.pros.length > 0 ? (
                <ul className="mt-6 space-y-3">
                  {product.pros.map(
                    (
                      item,
                      index,
                    ) => (
                      <li
                        key={
                          `${index}-${item}`
                        }
                        className="flex gap-3 rounded-2xl bg-emerald-50/70 p-4 text-sm font-semibold leading-6 text-emerald-950"
                      >
                        <span className="font-black text-emerald-600">
                          ✓
                        </span>

                        <span>
                          {item}
                        </span>
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm font-medium text-slate-500">
                  Chưa có dữ liệu ưu điểm.
                </p>
              )}
            </section>


            {/* CONS */}
            <section className="rounded-[32px] border border-amber-200 bg-white p-6 shadow-sm lg:p-8">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-2xl">
                  ⚠️
                </div>

                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-amber-600">
                    Lưu ý
                  </p>

                  <h2 className="text-xl font-black text-slate-950">
                    Nhược điểm
                  </h2>
                </div>
              </div>


              {product.cons.length > 0 ? (
                <ul className="mt-6 space-y-3">
                  {product.cons.map(
                    (
                      item,
                      index,
                    ) => (
                      <li
                        key={
                          `${index}-${item}`
                        }
                        className="flex gap-3 rounded-2xl bg-amber-50/70 p-4 text-sm font-semibold leading-6 text-amber-950"
                      >
                        <span className="font-black text-amber-600">
                          •
                        </span>

                        <span>
                          {item}
                        </span>
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm font-medium text-slate-500">
                  Chưa ghi nhận điểm hạn chế đáng chú ý.
                </p>
              )}
            </section>
          </div>


          {/* MERCHANT OFFERS */}
          <section className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm lg:p-8">

            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-600">
                  Merchant Offers
                </p>

                <h2 className="mt-2 text-2xl font-black text-slate-950">
                  So sánh nơi bán
                </h2>

                <p className="mt-2 text-sm text-slate-500">
                  Các nguồn được sắp xếp theo giá thấp nhất hiện tìm thấy.
                </p>
              </div>

              <div className="rounded-full bg-slate-100 px-4 py-2 text-xs font-black text-slate-600">
                {sortedOffers.length} nguồn
              </div>
            </div>


            {sortedOffers.length > 0 ? (
              <div className="mt-7 overflow-hidden rounded-3xl border border-slate-200">

                {sortedOffers.map(
                  (
                    offer,
                    index,
                  ) => (
                    <div
                      key={
                        offer.id
                      }
                      className={[
                        "flex flex-col gap-5 p-5",
                        "sm:flex-row sm:items-center sm:justify-between",

                        index
                        < sortedOffers.length - 1
                          ? "border-b border-slate-200"
                          : "",

                        index === 0
                          ? "bg-blue-50/60"
                          : "bg-white",
                      ].join(" ")}
                    >

                      {/* MERCHANT */}
                      <div className="min-w-0 flex-1">

                        <div className="flex flex-wrap items-center gap-2">

                          <h3 className="truncate text-base font-black text-slate-950">
                            {merchantName(
                              offer
                            )}
                          </h3>

                          {index === 0 && (
                            <span className="rounded-full bg-blue-600 px-3 py-1 text-[10px] font-black uppercase tracking-wide text-white">
                              Giá tốt nhất
                            </span>
                          )}

                          <span
                            className={[
                              "rounded-full border px-3 py-1",
                              "text-[10px] font-black",
                              availabilityClass(
                                offer.availability
                              ),
                            ].join(" ")}
                          >
                            {availabilityLabel(
                              offer.availability
                            )}
                          </span>
                        </div>


                        {offer.source_title && (
                          <p className="mt-2 line-clamp-1 text-xs font-medium text-slate-500">
                            {offer.source_title}
                          </p>
                        )}


                        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-400">

                          {offer.source_domain && (
                            <span>
                              🌐 {offer.source_domain}
                            </span>
                          )}

                          {offer.source_reliability_score != null && (
                            <span>
                              🛡️ Tin cậy{" "}
                              {Math.round(
                                offer.source_reliability_score
                              )}%
                            </span>
                          )}

                          <span>
                            🕒{" "}
                            {formatDate(
                              offer.last_checked_at
                            )}
                          </span>
                        </div>
                      </div>


                      {/* PRICE */}
                      <div className="shrink-0 sm:text-right">

                        <p className="text-xl font-black text-blue-600">
                          {formatPrice(
                            offer.price,
                            offer.currency,
                          )}
                        </p>

                        {offer.product_url ? (
                          <a
                            href={
                              offer.product_url
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-3 inline-flex rounded-xl bg-slate-950 px-5 py-2.5 text-xs font-black text-white transition hover:bg-blue-600"
                          >
                            Xem sản phẩm ↗
                          </a>
                        ) : (
                          <span className="mt-3 inline-flex rounded-xl bg-slate-100 px-5 py-2.5 text-xs font-bold text-slate-400">
                            Chưa có link
                          </span>
                        )}
                      </div>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <EmptyBlock
                icon="🛒"
                title="Chưa tìm thấy nơi bán"
                description="Hệ thống hiện chưa thu thập được nguồn bán cho sản phẩm này."
              />
            )}
          </section>


          {/* DATA INFORMATION */}
          <section className="rounded-[32px] border border-slate-200 bg-slate-950 p-7 text-white lg:p-8">
            <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">

              <div>
                <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-300">
                  Smart Shopping AI
                </p>

                <h2 className="mt-3 text-2xl font-black">
                  Thông tin sản phẩm được tổng hợp từ Internet
                </h2>

                <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
                  Hệ thống phân tích nhu cầu mua hàng,
                  tìm kiếm nguồn thực tế, chuẩn hóa dữ liệu,
                  so sánh giá và hỗ trợ người dùng lựa chọn
                  sản phẩm phù hợp.
                </p>
              </div>


              <div className="space-y-3">
                <DataRow
                  label="Mã sản phẩm"
                  value={
                    `#${product.id}`
                  }
                />

                <DataRow
                  label="Danh mục"
                  value={
                    product.category
                    || "Chưa rõ"
                  }
                />

                <DataRow
                  label="Cập nhật"
                  value={
                    formatDate(
                      product.updated_at
                    )
                  }
                />

                <DataRow
                  label="Số nguồn"
                  value={
                    String(
                      sortedOffers.length
                    )
                  }
                />
              </div>
            </div>
          </section>


          {/* BACK */}
          <div className="pb-8 text-center">
            <button
              type="button"
              onClick={() =>
                router.back()
              }
              className="rounded-2xl border border-slate-300 bg-white px-7 py-3 text-sm font-black text-slate-700 transition hover:border-blue-300 hover:text-blue-600"
            >
              ← Quay lại danh sách đề xuất
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}


/* =========================================================
   SMALL COMPONENTS
========================================================= */

function InfoCard({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[26px] border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">

      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-50 text-xl">
        {icon}
      </div>

      <p className="mt-4 text-xs font-black uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 line-clamp-2 font-black text-slate-950">
        {value}
      </p>
    </div>
  );
}


function EmptyBlock({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mt-7 rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">

      <div className="text-4xl">
        {icon}
      </div>

      <h3 className="mt-4 font-black text-slate-800">
        {title}
      </h3>

      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-500">
        {description}
      </p>
    </div>
  );
}


function DataRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl bg-white/5 px-4 py-3">

      <span className="text-xs font-bold text-slate-400">
        {label}
      </span>

      <span className="text-right text-sm font-black text-white">
        {value}
      </span>
    </div>
  );
}