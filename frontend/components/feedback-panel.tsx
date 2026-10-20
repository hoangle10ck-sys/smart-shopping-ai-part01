"use client";

import { useState } from "react";
import { createFeedback } from "@/lib/api";

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

export function FeedbackPanel({ sessionId, productId }: FeedbackPanelProps) {
  const [submitted, setSubmitted] = useState(false);
  const [negative, setNegative] = useState(false);
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setError("Chưa gửi được phản hồi. Vui lòng thử lại.");
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
        reason: reason || null,
        comment: comment || null,
      });

      setSubmitted(true);
    } catch {
      setError("Chưa gửi được phản hồi. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div
        role="status"
        className="mt-3.5 rounded-xl border border-[#cbe3d3] bg-[#ecf7f0] px-4 py-2.5 text-center text-xs font-semibold text-[#165b39]"
      >
        ✓ Cảm ơn bạn đã phản hồi
      </div>
    );
  }

  return (
    <div className="mt-3.5 border-t border-[var(--line)] pt-3.5">
      <p className="text-center text-[11px] font-semibold text-[var(--muted)]">
        Đề xuất này có hữu ích không?
      </p>

      <div className="mt-2.5 grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={submitHelpful}
          className="btn btn-secondary !min-h-[36px] !px-2 !py-1 !text-xs font-medium hover:border-[var(--brand)]"
        >
          👍 Hữu ích
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => setNegative(!negative)}
          aria-pressed={negative}
          className={`btn btn-secondary !min-h-[36px] !px-2 !py-1 !text-xs font-medium ${
            negative ? "!border-[var(--line-strong)] !bg-[#f0f4f1]" : ""
          }`}
        >
          👎 Không phù hợp
        </button>
      </div>

      {negative && (
        <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-3 transition-all">
          <p className="text-[11px] font-bold text-[var(--foreground)]">Lý do:</p>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {reasons.map((item) => (
              <button
                key={item}
                type="button"
                disabled={loading}
                aria-pressed={reason === item}
                onClick={() => setReason(item)}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-all ${
                  reason === item
                    ? "border-[var(--brand)] bg-[var(--brand)] text-white shadow-xs"
                    : "border-[var(--line)] bg-white text-[var(--foreground)] hover:border-[var(--line-strong)]"
                }`}
              >
                {item}
              </button>
            ))}
          </div>

          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={2}
            aria-label="Ý kiến thêm"
            disabled={loading}
            placeholder="Ý kiến thêm..."
            className="mt-2.5 w-full resize-none rounded-lg border border-[var(--line)] bg-white p-2.5 text-xs text-[var(--foreground)] outline-none transition focus:border-[var(--brand)] focus:ring-1 focus:ring-[var(--brand)]"
          />

          <button
            type="button"
            disabled={loading}
            onClick={submitNegative}
            className="btn btn-primary mt-2.5 w-full !min-h-[34px] !py-1 !text-xs font-semibold"
          >
            {loading ? "Đang gửi..." : "Gửi phản hồi"}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-[11px] font-semibold text-red-600 text-center">
          {error}
        </p>
      )}
    </div>
  );
}
