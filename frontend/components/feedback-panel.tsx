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
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Không gửi được phản hồi.",
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
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Không gửi được phản hồi.",
      );
    } finally {
      setLoading(false);
    }
  }


  if (submitted) {
    return (
      <div className="mt-4 rounded-2xl bg-emerald-50 px-4 py-3 text-center text-sm font-bold text-emerald-700">
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
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100"
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
          className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-700 transition hover:bg-red-100"
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
                  onClick={() =>
                    setReason(item)
                  }
                  className={[
                    "rounded-full border px-3 py-1.5 text-xs font-semibold",

                    reason === item
                      ? "border-blue-600 bg-blue-600 text-white"
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
            placeholder="Ý kiến thêm..."
            className="mt-3 w-full resize-none rounded-xl border border-slate-200 bg-white p-3 text-xs outline-none focus:border-blue-400"
          />

          <button
            type="button"
            disabled={loading}
            onClick={
              submitNegative
            }
            className="mt-3 w-full rounded-xl bg-slate-950 px-4 py-2.5 text-xs font-extrabold text-white transition hover:bg-blue-600 disabled:opacity-50"
          >
            {loading
              ? "Đang gửi..."
              : "Gửi phản hồi"}
          </button>
        </div>
      )}

      {error && (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}