import type { RecommendationItem } from "@/types/shopping";
import { RequirementMatches } from "@/components/requirement-matches";
import { displayScore, record, safeHttpUrl, scoreRows, textList } from "@/lib/results-utils";

function Notes({ title, items }: { title: string; items: string[] }) {
  return items.length ? <div className="mt-3"><h4 className="font-bold">{title}</h4><ul className="mt-1 list-disc space-y-1 pl-5">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null;
}

export function RecommendationDetails({ product }: { product: RecommendationItem }) {
  const explanation = record(product.explanation), evidence = record(product.evidence);
  const url = safeHttpUrl(product.product_url);
  const timestamp = product.last_checked_at ? new Date(product.last_checked_at) : null;
  const modeNames: Record<string, string> = { demo: "Giải thích Demo", openai: "Giải thích OpenAI", gemini: "Giải thích Gemini", fallback: "Giải thích dự phòng deterministic" };
  const summary = typeof explanation.summary === "string" ? explanation.summary : typeof product.explanation === "string" ? product.explanation : null;
  const whyFit = textList(explanation.why_fit);
  return (
    <div className="mt-5 space-y-3 text-sm text-slate-700">
      <section aria-label="Mức đáp ứng yêu cầu" className="rounded-2xl border border-slate-200 p-4">
        <h3 className="font-bold text-slate-950">Mức đáp ứng yêu cầu</h3>
        <RequirementMatches items={product.requirement_matches} />
      </section>
      <details className="rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer font-bold text-slate-950">Điểm thành phần</summary>
        <p className="mt-3">Final AI Match: <strong>{displayScore(product.score?.final_score)}</strong></p>
        <p className="mt-2 text-xs text-slate-500">Các thành phần dưới đây là điểm gốc chuẩn hóa 0–100, chưa nhân trọng số. Final AI Match dùng nguyên giá trị backend, không tính lại trên trình duyệt.</p>
        <table className="mt-3 w-full text-left text-xs">
          <caption className="sr-only">Điểm gốc và trọng số</caption>
          <thead><tr><th scope="col">Thành phần</th><th scope="col">Điểm gốc</th><th scope="col">Trọng số</th></tr></thead>
          <tbody>{scoreRows(product.score).map((row) => <tr key={row.key} className="border-t border-slate-100"><th scope="row" className="py-2 font-medium">{row.label}</th><td>{displayScore(row.value)}</td><td>{row.weight}%</td></tr>)}</tbody>
        </table>
      </details>
      <details className="rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer font-bold text-slate-950">Vì sao được đề xuất?</summary>
        <p className="mt-3">{summary || "Backend chưa cung cấp phần tóm tắt giải thích."}</p>
        {typeof explanation.generation_mode === "string" && <p className="mt-2 text-xs text-slate-500">{modeNames[explanation.generation_mode] || "Chưa rõ cách tạo giải thích"}</p>}
        <Notes title="Lý do phù hợp" items={whyFit} />
        <Notes title="Ưu điểm" items={[...textList(product.pros), ...textList(explanation.pros)]} />
        <Notes title="Hạn chế / đánh đổi" items={[...textList(product.cons), ...textList(explanation.cons), ...textList(explanation.tradeoffs)]} />
        <Notes title="Lưu ý từ backend" items={[...textList(explanation.cautions), ...textList(explanation.evidence_notes)]} />
      </details>
      <details className="rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer font-bold text-slate-950">Nguồn và bằng chứng</summary>
        {product.evidence?.fields?.length ? <ul aria-label="Bằng chứng theo trường" className="mt-3 space-y-3 break-words">
          {product.evidence.fields.map((field, index) => {
            const fieldUrl = safeHttpUrl(field.url);
            return <li key={index} className="rounded-xl bg-slate-50 p-3">
              <p className="font-bold">{field.field}: {field.value}</p>
              <p>Nguồn: {field.source || "Chưa cung cấp"}</p>
              <p>Domain: {field.domain || "Chưa cung cấp"} · Merchant: {field.merchant || "Chưa cung cấp"}</p>
              <p>Thời điểm thu thập: {field.retrieved_at || "Chưa cung cấp"}</p>
              {field.reliability != null && <p>Độ tin cậy nguồn: {field.reliability}/100</p>}
              {fieldUrl && <a href={fieldUrl} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{fieldUrl}</a>}
            </li>;
          })}
        </ul> : <p className="mt-3 text-slate-500">Chưa có evidence có cấu trúc cho kết quả này.</p>}
        <dl className="mt-3 space-y-2 break-words">
          <div><dt className="text-slate-500">Merchant / cửa hàng</dt><dd>{product.merchant || "Chưa được cung cấp"}</dd></div>
          <div><dt className="text-slate-500">Domain của URL sản phẩm</dt><dd>{url ? new URL(url).hostname : "Chưa có URL hợp lệ"}</dd></div>
          <div><dt className="text-slate-500">Lần kiểm tra offer ghi trong snapshot</dt><dd>{timestamp && !Number.isNaN(timestamp.getTime()) ? timestamp.toLocaleString("vi-VN") : "Backend chưa lưu thời điểm kiểm tra cho kết quả này"}</dd></div>
          <div><dt className="text-slate-500">URL sản phẩm</dt><dd>{url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{url}</a> : "Chưa được cung cấp"}</dd></div>
        </dl>
        <Notes title="Bằng chứng giá / rating / thông số từ backend" items={textList(evidence.supporting_evidence)} />
        {!textList(evidence.supporting_evidence).length && <p className="mt-3 text-slate-500">Chưa có bằng chứng chi tiết được backend cung cấp.</p>}
        <Notes title="Cảnh báo dữ liệu" items={textList(evidence.warnings)} />
        <p className="mt-3 text-xs text-slate-500">Thông tin thuộc kết quả đã lưu; không khẳng định giá hiện tại của cửa hàng.</p>
      </details>
    </div>
  );
}
