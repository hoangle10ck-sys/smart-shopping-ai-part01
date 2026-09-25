"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getHistory } from "@/lib/api";
import { EmptyState, ErrorState } from "@/components/ui-state";
import { PipelineProgress } from "@/components/pipeline-progress";
import { Icon } from "@/components/icon";
import type { HistoryItem, HistoryListResponse } from "@/types/history";

const statusLabels: Record<HistoryItem["status"], string> = { PENDING: "Chờ tìm kiếm", PROCESSING: "Đang xử lý", COMPLETED: "Hoàn thành", FAILED: "Tìm kiếm gặp lỗi" };
type HistoryState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: HistoryListResponse };
export default function HistoryPage() {
  const [state, setState] = useState<HistoryState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getHistory(controller.signal).then(
      data => { if (!controller.signal.aborted) setState({ kind: "ready", data }); },
      () => { if (!controller.signal.aborted) setState({ kind: "error" }); },
    );
    return () => controller.abort();
  }, [attempt]);
  return <main id="main-content" tabIndex={-1}>
    <section className="page-heading"><div className="page-container"><p className="eyebrow">Những lựa chọn đã khám phá</p><h1 className="page-title mt-3">Lịch sử tìm kiếm</h1><p className="muted mt-3 text-sm">Xem lại 50 phiên gần đây cùng những đề xuất đã lưu.</p></div></section>
    <div className="page-container page-content">
      {state.kind === 'loading' && <PipelineProgress phase="read" />}
      {state.kind === 'error' && <ErrorState title="Không thể tải lịch sử" retry={() => { setState({kind:'loading'}); setAttempt(value => value+1); }} />}
      {state.kind === 'ready' && !state.data.items.length && <EmptyState title="Bạn chưa có lịch sử tìm kiếm." description="Bắt đầu từ điều bạn cần. Những tìm kiếm của bạn sẽ được lưu ở đây." action={<Link href="/" className="btn btn-primary">Bắt đầu tìm kiếm</Link>} />}
      {state.kind === 'ready' && !!state.data.items.length && <ul className="space-y-3">{state.data.items.map(item => <li key={item.session_id} className="surface p-5 sm:p-6">
        <div className="flex gap-4"><span className="hidden size-11 shrink-0 items-center justify-center rounded-xl bg-[#eef4ea] text-[#43714e] sm:flex"><Icon name="clock" /></span><div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2"><time dateTime={item.created_at} className="muted text-xs">{new Intl.DateTimeFormat('vi-VN', {dateStyle:'medium',timeStyle:'short'}).format(new Date(item.created_at))}</time><span className={`tag ${item.status === 'FAILED' ? 'tag-amber' : item.status === 'COMPLETED' ? 'tag-green' : ''}`}>{statusLabels[item.status]}</span></div>
          <h2 className="mt-3 text-base font-semibold">{item.raw_query}</h2>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="muted text-xs">{item.recommendation_count} đề xuất đã lưu</p><Link href={`/results/${encodeURIComponent(item.session_id)}`} aria-label={`Xem lại: ${item.raw_query}`} className="btn btn-secondary">Xem lại <Icon name="arrow" width="16" height="16" /></Link></div>
        </div></div>
      </li>)}</ul>}
    </div>
  </main>;
}
