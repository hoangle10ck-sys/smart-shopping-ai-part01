"use client";

import {
  useState,
} from "react";

import {
  createFeedback,
} from "@/lib/api";


interface FeedbackPanelProps {
  sessionId: string;
  productId: number;
}


const reasons = [
  "Giá cao",
  "Không đúng nhu cầu",
  "Thông tin chưa đủ",
  "Không thích thương hiệu",
  "Khác",
];


export function FeedbackPanel({
  sessionId,
  productId,
}: FeedbackPanelProps) {
  const [submitted, setSubmitted] =
    useState(false);

  const [negative, setNegative] =
    useState(false);

  const [reason, setReason] =
    useState("");

  const [comment, setComment] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  async function submitHelpful() {
    setLoading(true);
    setError(null);

    try {
      await createFeedback({
        session_id: sessionId,
        product_id: productId,
        is_helpful: true,
      });

      setSubmitted(true);
    } catch {
      setError(
        "Chưa gửi được phản hồi. Vui lòng thử lại.",
      );
    } finally {
      setLoading(false);
    }
  }


  async function submitNegative() {
    setLoading(true);
    setError(null);

    try {
      await createFeedback({
        session_id: sessionId,
        product_id: productId,
        is_helpful: false,
        reason:
          reason || null,
        comment:
          comment || null,
      });

      setSubmitted(true);
    } catch {
      setError(
        "Chưa gửi được phản hồi. Vui lòng thử lại.",
      );
    } finally {
      setLoading(false);
    }
  }


  if (submitted) {
    return (
      <div role="status" className="mt-4 rounded-xl bg-[#eaf3e8] px-4 py-3 text-center text-xs font-semibold text-[#245b38]">
        ✓ Cảm ơn bạn đã phản hồi
      </div>
    );
  }


  return (
    <div className="mt-4 border-t border-slate-100 pt-4">
      <p className="text-center text-xs font-bold text-slate-500">
        Đề xuất này có hữu ích không?
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={submitHelpful}
          className="btn btn-secondary !px-2 !text-xs"
        >
          👍 Hữu ích
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() =>
            setNegative(
              !negative,
            )
          }
          aria-pressed={negative} className="btn btn-secondary !px-2 !text-xs"
        >
          👎 Không phù hợp
        </button>
      </div>


      {negative && (
        <div className="mt-4 rounded-2xl bg-slate-50 p-3">
          <p className="text-xs font-bold text-slate-600">
            Lý do:
          </p>

          <div className="mt-2 flex flex-wrap gap-2">
            {reasons.map(
              (item) => (
                <button
                  key={item}
                  type="button"
                  disabled={loading} aria-pressed={reason === item} onClick={() => setReason(item)}
                  className={[
                    "rounded-full border px-3 py-1.5 text-xs font-semibold",

                    reason === item
                      ? "border-[#165b46] bg-[#165b46] text-white"
                      : "border-slate-200 bg-white text-slate-600",
                  ].join(" ")}
                >
                  {item}
                </button>
              ),
            )}
          </div>

          <textarea
            value={comment}
            onChange={(event) =>
              setComment(
                event.target.value,
              )
            }
            rows={2}
            aria-label="Ý kiến thêm" disabled={loading} placeholder="Ý kiến thêm..."
            className="mt-3 w-full resize-none rounded-xl border border-slate-200 bg-white p-3 text-xs outline-none focus:border-blue-400"
          />

          <button
            type="button"
            disabled={loading}
            onClick={
              submitNegative
            }
            className="btn btn-primary mt-3 w-full"
          >
            {loading
              ? "Đang gửi..."
              : "Gửi phản hồi"}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-xs font-semibold text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
