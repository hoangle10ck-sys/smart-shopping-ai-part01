export type PipelinePhase = "analyze" | "search" | "read" | "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
const messages: Record<PipelinePhase, string> = {
  analyze: "Đang phân tích nhu cầu…",
  search: "Đang tìm kiếm và đánh giá sản phẩm…",
  read: "Đang tải kết quả đã lưu…",
  PENDING: "Phiên đang chờ hoàn thiện nhu cầu.",
  PROCESSING: "Tìm kiếm đang được xử lý. Tải lại để kiểm tra kết quả.",
  COMPLETED: "Đã hoàn thành tìm kiếm.",
  FAILED: "Lần tìm kiếm gần nhất gặp lỗi. Kết quả thành công trước đó, nếu có, vẫn được giữ.",
};
export function PipelineProgress({ phase }: { phase: PipelinePhase }) {
  const waiting = ['analyze', 'search', 'read', 'PROCESSING'].includes(phase);
  return <section role="status" aria-live="polite" className={`mb-5 rounded-2xl border p-5 text-left ${phase === 'FAILED' ? 'border-amber-200 bg-amber-50' : 'border-[#dce4de] bg-white'}`}>
    <div className="flex items-center gap-3">{waiting && <span aria-hidden="true" className="size-5 shrink-0 animate-spin rounded-full border-2 border-[#d5e2d3] border-t-[#165b46]" />}<p className="text-sm font-semibold">{messages[phase]}</p></div>
    {waiting && <><p className="muted mt-2 text-xs">{phase === 'search' ? 'Tìm nguồn, kiểm tra thông tin và xếp hạng có thể mất một chút thời gian.' : 'Bạn không cần gửi lại yêu cầu trong lúc chờ.'}</p><div aria-hidden="true" className="mt-5 grid grid-cols-3 gap-3">{[1,2,3].map(i => <div key={i} className="space-y-2"><div className="skeleton h-14" /><div className="skeleton h-2 w-3/4" /></div>)}</div></>}
  </section>;
}
