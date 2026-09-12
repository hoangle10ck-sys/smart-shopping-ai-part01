export type PipelinePhase = "analyze" | "search" | "read" | "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

const messages: Record<PipelinePhase, string> = {
  analyze: "Đang chờ backend phân tích nhu cầu và tạo truy vấn…",
  search: "Đang chờ kết quả tìm kiếm và xếp hạng từ backend…",
  read: "Đang tải kết quả đã lưu của phiên, không chạy lại tìm kiếm…",
  PENDING: "Phiên đang chờ hoàn thiện nhu cầu hoặc bắt đầu tìm kiếm.",
  PROCESSING: "Backend báo phiên đang xử lý. Bạn có thể tải lại để kiểm tra trạng thái.",
  COMPLETED: "Backend đã trả kết quả hoàn thành; dữ liệu có thể đến từ cache hợp lệ.",
  FAILED: "Lần tìm kiếm gần nhất gặp lỗi. Kết quả thành công trước đó, nếu có, vẫn được giữ.",
};

export function PipelineProgress({ phase }: { phase: PipelinePhase }) {
  return <section role="status" aria-live="polite" className="mb-6 rounded-2xl border border-blue-100 bg-blue-50 p-5 text-left">
    <p className="font-bold text-slate-900">{messages[phase]}</p>
    <p className="mt-2 text-xs text-slate-600">Quy trình tham khảo — backend chưa cung cấp tiến độ realtime cho từng bước:</p>
    <ol className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
      {["Phân tích nhu cầu", "Tạo truy vấn", "Tìm kiếm", "Thu thập sản phẩm", "Chuẩn hóa", "Lọc", "Chấm điểm", "Xếp hạng", "Hoàn thành"].map((step, index) =>
        <li key={step} className="rounded-lg border border-blue-100 bg-white px-2 py-1">{index + 1}. {step}</li>)}
    </ol>
  </section>;
}
