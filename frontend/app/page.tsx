"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/icon";
import { PipelineProgress } from "@/components/pipeline-progress";
import { analyzeRequirement, executeSearch, searchErrorMessage } from "@/lib/api";

const examples = [
  "Máy tính",
  "Điện thoại khoảng 10 triệu, camera tốt, pin lâu",
  "Laptop khoảng 20 triệu để học lập trình",
  "TV khoảng 10 triệu để xem phim",
];

export default function Home() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<"analyze" | "search">("analyze");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 2) {
      setError("Hãy nhập tên sản phẩm bạn muốn tìm.");
      return;
    }

    setLoading(true);
    setError(null);
    setPhase("analyze");
    try {
      const analyzed = await analyzeRequirement(value);
      if (!analyzed.session_id) throw new Error("Không thể tạo phiên tìm kiếm.");
      if (analyzed.needs_clarification) {
        throw new Error(analyzed.clarification_question || "Chưa nhận diện được sản phẩm. Hãy thử nhập tên cụ thể, ví dụ: máy tính hoặc điện thoại.");
      }

      setPhase("search");
      const result = await executeSearch(analyzed.session_id);
      if (!result.session_id) throw new Error("Tìm kiếm chưa trả về phiên kết quả.");
      router.push(`/results/${result.session_id}`);
    } catch (caught) {
      setError(searchErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section className="page-container pt-12 sm:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Mua sắm thông minh</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Bạn đang cần tìm gì?</h1>
          <p className="muted mx-auto mt-4 max-w-xl">
            Nhập tên sản phẩm hoặc mô tả nhu cầu. Hệ thống sẽ tự phân tích, tìm kiếm và đề xuất lựa chọn phù hợp.
          </p>

          <form onSubmit={handleSubmit} className="surface mt-8 p-5 text-left shadow-md sm:p-7">
            <label htmlFor="shopping-query" className="field-label">Mô tả sản phẩm bạn muốn tìm</label>
            <textarea
              id="shopping-query"
              aria-label="Bạn đang tìm sản phẩm gì?"
              value={query}
              onChange={(event) => { setQuery(event.target.value); setError(null); }}
              rows={4}
              disabled={loading}
              placeholder="Ví dụ: Máy tính; hoặc laptop khoảng 20 triệu để học lập trình…"
              className="field mt-2"
            />

            {error && <p role="alert" className="mt-4 text-sm font-medium text-red-700">{error}</p>}
            {loading && <div className="mt-4"><PipelineProgress phase={phase} /></div>}

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="muted text-xs">Tự tìm trong dữ liệu và các nguồn trực tuyến khả dụng; mức độ bao phủ tùy nguồn có thể truy cập.</p>
              <button type="submit" disabled={loading || query.trim().length < 2} className="btn btn-primary">
                <Icon name="search" width="16" height="16" />
                <span>{loading ? "Đang phân tích và tìm…" : "Tìm và đề xuất"}</span>
                <Icon name="arrow" width="16" height="16" />
              </button>
            </div>
          </form>

          <section aria-label="Gợi ý tìm kiếm" className="mt-6">
            <p className="muted mb-3 text-xs font-semibold">Thử tìm nhanh</p>
            <div className="flex flex-wrap justify-center gap-2">
              {examples.map((example) => (
                <button key={example} type="button" disabled={loading} onClick={() => { setQuery(example); setError(null); }} className="btn btn-secondary !min-h-9 !rounded-full !px-4 !py-1.5 !text-xs">
                  {example}
                </button>
              ))}
            </div>
          </section>
        </div>
      </section>

      <section id="how-it-works" className="page-container py-16 sm:py-20">
        <div className="mb-10 text-center">
          <p className="eyebrow">Quy trình tự động</p>
          <h2 className="mt-2 text-2xl font-bold">Từ câu lệnh đến gợi ý mua sắm</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {[
            { icon: "search", title: "Nhập điều bạn cần", text: "Tên sản phẩm là đủ; ngân sách và mục đích chỉ giúp đề xuất sát hơn." },
            { icon: "layers", title: "Tự động tìm kiếm", text: "Hệ thống phân tích yêu cầu và kiểm tra các nguồn dữ liệu khả dụng." },
            { icon: "shield", title: "Xem đề xuất có cơ sở", text: "Đối chiếu sản phẩm với tiêu chí và bằng chứng thu thập được." },
          ].map((item) => (
            <div key={item.title} className="surface p-6">
              <Icon name={item.icon} width="20" height="20" />
              <h3 className="mt-4 font-bold">{item.title}</h3>
              <p className="muted mt-2 text-sm">{item.text}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}