"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { getHistory } from "@/lib/api";
import type { HistoryItem, HistoryListResponse } from "@/types/history";

const statusLabels: Record<HistoryItem["status"], string> = {
  PENDING: "Chờ tìm kiếm",
  PROCESSING: "Đang xử lý",
  COMPLETED: "Hoàn thành",
  FAILED: "Tìm kiếm gặp lỗi",
};

type HistoryState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: HistoryListResponse };

export default function HistoryPage() {
  const [state, setState] = useState<HistoryState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getHistory(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ kind: "ready", data });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ kind: "error", message: error instanceof Error ? error.message : "Không thể tải lịch sử." });
        }
      },
    );
    return () => controller.abort();
  }, [attempt]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-5 py-10 lg:px-8">
        <h1 className="text-3xl font-extrabold">Lịch sử tìm kiếm</h1>
        <p className="mt-2 text-slate-500">Xem lại 50 phiên tìm kiếm gần đây và các đề xuất đã lưu.</p>

        {state.kind === "loading" && (
          <p role="status" className="mt-8 rounded-2xl bg-white p-6">Đang tải lịch sử…</p>
        )}

        {state.kind === "error" && (
          <div role="alert" className="mt-8 rounded-2xl border border-red-200 bg-white p-6">
            <p className="text-red-700">{state.message}</p>
            <button
              type="button"
              onClick={() => { setState({ kind: "loading" }); setAttempt((value) => value + 1); }}
              className="mt-4 rounded-xl bg-blue-600 px-5 py-2 font-semibold text-white"
            >
              Thử lại
            </button>
          </div>
        )}

        {state.kind === "ready" && state.data.items.length === 0 && (
          <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-8 text-center">
            <p className="font-semibold">Bạn chưa có lịch sử tìm kiếm.</p>
            <Link href="/" className="mt-4 inline-block font-semibold text-blue-600">Bắt đầu tìm kiếm</Link>
          </div>
        )}

        {state.kind === "ready" && state.data.items.length > 0 && (
          <ul className="mt-8 space-y-4">
            {state.data.items.map((item) => (
              <li key={item.session_id} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  <time dateTime={item.created_at} className="text-slate-500">
                    {new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}
                  </time>
                  <span className={item.status === "FAILED" ? "font-semibold text-red-700" : "font-semibold text-slate-600"}>
                    {statusLabels[item.status]}
                  </span>
                </div>
                <h2 className="mt-3 break-words text-lg font-bold">{item.raw_query}</h2>
                <div className="mt-4 flex items-center justify-between gap-4">
                  <p className="text-sm text-slate-500">{item.recommendation_count} đề xuất đã lưu</p>
                  <Link
                    href={`/results/${encodeURIComponent(item.session_id)}`}
                    aria-label={`Xem lại: ${item.raw_query}`}
                    className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                  >
                    Xem lại
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
