"use client";

import { useState, useEffect } from "react";
import type { FormEvent } from "react";
import { PipelineProgress } from "@/components/pipeline-progress";
import { Icon } from "@/components/icon";
import { useRouter } from "next/navigation";
import {
  analyzeRequirement,
  clarifyRequirement,
  executeSearch,
  researchSearch,
  researchStatus,
  searchErrorMessage,
} from "@/lib/api";

const examples = [
  "Điện thoại khoảng 10 triệu, camera tốt, pin lâu",
  "Laptop khoảng 20 triệu để học lập trình",
  "TV khoảng 10 triệu để xem phim",
  "Xe máy khoảng 33 triệu để đi học",
];

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<"default" | "research">("default");
  const [serverMode, setServerMode] = useState<"demo" | "live" | null>(null);

  useEffect(() => {
    let active = true;
    researchStatus().then((status) => {
      if (active) setServerMode(status.default_mode);
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  const [pipelinePhase, setPipelinePhase] = useState<"analyze" | "search">("analyze");
  const [directUrl, setDirectUrl] = useState("");
  const [sourcePlatforms, setSourcePlatforms] = useState<("shopee" | "lazada")[]>(["shopee", "lazada"]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /*
   * Clarification state
   */
  const [clarificationSessionId, setClarificationSessionId] = useState<string | null>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [clarificationRound, setClarificationRound] = useState(0);

  /*
   * SEARCH MỚI
   */
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const value = query.trim();

    if (value.length < 5) {
      setError("Hãy mô tả nhu cầu chi tiết hơn một chút.");
      return;
    }

    /*
     * Reset clarification cũ
     */
    setClarificationSessionId(null);
    setClarificationQuestion(null);
    setClarificationAnswer("");
    setClarificationRound(0);

    setError(null);
    setLoading(true);
    setPipelinePhase("analyze");

    try {
      if (mode === "research") {
        setPipelinePhase("search");
        const result = await researchSearch(value);
        router.push(`/results/${result.session_id}`);
        return;
      }

      console.log("[Smart Shopping] Analyze:", value);

      const analyzed = await analyzeRequirement(value);
      console.log("[Smart Shopping] Analyze response:", analyzed);

      if (!analyzed.session_id) {
        throw new Error("Backend không trả về session_id.");
      }

      /*
       * AI thiếu thông tin -> yêu cầu làm rõ
       */
      if (analyzed.needs_clarification) {
        setClarificationSessionId(analyzed.session_id);
        setClarificationQuestion(
          analyzed.clarification_question ??
            "Bạn có thể bổ sung thêm mục đích sử dụng, ngân sách hoặc yêu cầu quan trọng không?"
        );
        setClarificationRound(1);
        return;
      }

      /*
       * Đủ thông tin -> chạy search
       */
      await runSearch(analyzed.session_id);
    } catch (caught) {
      console.error("[Smart Shopping] Error:", caught);
      setError(searchErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  /*
   * GỬI CÂU TRẢ LỜI CHO AI
   */
  async function handleClarification() {
    const answer = clarificationAnswer.trim();

    if (!clarificationSessionId) {
      setError("Phiên phân tích không hợp lệ.");
      return;
    }

    if (answer.length < 2) {
      setError("Hãy nhập thêm thông tin để AI tiếp tục phân tích.");
      return;
    }

    setError(null);
    setLoading(true);
    setPipelinePhase("analyze");

    try {
      console.log("[Smart Shopping] Clarification:", {
        sessionId: clarificationSessionId,
        answer,
      });

      const clarified = await clarifyRequirement(clarificationSessionId, answer);
      console.log("[Smart Shopping] Clarification response:", clarified);

      if (!clarified.session_id) {
        throw new Error("Backend không trả về session_id sau khi làm rõ.");
      }

      /*
       * Nếu AI vẫn thiếu thông tin -> tiếp tục hỏi
       */
      if (clarified.needs_clarification) {
        setClarificationSessionId(clarified.session_id);
        setClarificationQuestion(
          clarified.clarification_question ??
            "AI vẫn cần thêm một chút thông tin. Bạn có thể mô tả rõ hơn không?"
        );
        setClarificationAnswer("");
        setClarificationRound((current) => current + 1);
        return;
      }

      /*
       * Đã đủ thông tin
       */
      setClarificationSessionId(null);
      setClarificationQuestion(null);
      setClarificationAnswer("");

      /*
       * Chạy search
       */
      await runSearch(clarified.session_id);
    } catch (caught) {
      console.error("[Smart Shopping] Clarification error:", caught);
      setError("Chưa gửi được thông tin bổ sung. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  /*
   * SEARCH PIPELINE
   */
  async function runSearch(sessionId: string) {
    console.log("[Smart Shopping] Execute Search:", sessionId);

    setPipelinePhase("search");
    const searchResult = await executeSearch(sessionId, {
      directUrls: directUrl.trim() ? [directUrl.trim()] : [],
      sourcePlatforms,
    });

    console.log("[Smart Shopping] Search result:", searchResult);

    if (!searchResult.session_id) {
      throw new Error("Backend không trả về session_id sau khi tìm kiếm.");
    }

    router.push(`/results/${searchResult.session_id}`);
  }

  /*
   * Cho phép nhấn Enter trong clarification textarea
   */
  function handleClarificationKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!loading) {
        void handleClarification();
      }
    }
  }

  function chooseExample(example: string) {
    setQuery(example);
    setError(null);
    setClarificationSessionId(null);
    setClarificationQuestion(null);
    setClarificationAnswer("");
    setClarificationRound(0);
  }

  return (
    <main id="main-content" tabIndex={-1}>
      {/* Hero Section */}
      <section className="relative border-b border-[var(--line)] bg-gradient-to-b from-[#f2f7f4] via-[#f8faf8] to-[#ffffff] pb-16 pt-12 sm:pb-20 sm:pt-16">
        <div className="page-container">
          <div className="mx-auto max-w-3xl text-center">
            <span className="eyebrow inline-flex items-center gap-1.5 rounded-full bg-[var(--brand-light)] px-3.5 py-1 text-[var(--brand)] shadow-xs">
              <Icon name="spark" width="14" height="14" /> Trợ lý mua sắm thông minh
            </span>
            <h1 className="mt-5 text-[clamp(2.1rem,4.5vw,3.6rem)] font-bold leading-[1.14] tracking-[-0.04em] text-[var(--foreground)]">
              Tìm đúng sản phẩm.<br />
              <span className="text-[var(--brand)]">Đúng nhu cầu thực tế của bạn.</span>
            </h1>
            <p className="muted mx-auto mt-4 max-w-xl text-sm sm:text-base leading-relaxed">
              Mô tả điều bạn đang tìm bằng ngôn từ tự nhiên. Hệ thống phân tích yêu cầu, tra cứu đa nguồn và đối chiếu minh bạch để bạn chọn lựa có cơ sở.
            </p>
          </div>

          {/* Main Search Panel */}
          <div className="mx-auto mt-10 max-w-2xl">
            <form
              onSubmit={handleSubmit}
              className="surface overflow-hidden !rounded-2xl border-[var(--line)] p-5 shadow-[0_16px_40px_-20px_rgba(15,91,68,0.18)] sm:p-7"
              aria-busy={loading}
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <label htmlFor="shopping-query" className="font-semibold text-sm sm:text-base text-[var(--foreground)]">
                  Bạn đang tìm sản phẩm gì?
                </label>
                <span className="hidden items-center gap-1 text-[11px] font-medium text-[var(--muted)] sm:flex">
                  <Icon name="spark" width="13" height="13" className="text-[var(--brand)]" />
                  Phân tích theo nhu cầu
                </span>
              </div>

              <textarea
                id="shopping-query"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setError(null);
                }}
                rows={4}
                disabled={loading}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    if (!loading) event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Ví dụ: Tôi muốn tìm điện thoại khoảng 10 triệu, camera tốt, pin lâu để đi làm..."
                aria-describedby="search-hint"
                aria-invalid={!!error}
                className="field resize-y !rounded-xl !border-[#d6e0d9] !bg-[#fafcfb] !p-4 !text-sm sm:!text-base leading-relaxed focus:!bg-white"
              />

              <p id="search-hint" className="muted mt-2.5 text-xs">
                Gợi ý: Nêu rõ ngân sách dự kiến, mục đích sử dụng chính và các tính năng quan trọng.
              </p>

              <div className="mt-5 rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-4 text-xs">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="data-mode" className="field-label mb-1.5">Chế độ dữ liệu</label>
                    <select id="data-mode" className="field !h-10 !py-1.5 !text-xs" value={mode} disabled={loading}
                      onChange={(event) => { setMode(event.target.value as "default" | "research"); setClarificationSessionId(null); }}>
                      <option value="default">{serverMode === "live" ? "Live — theo cấu hình server, không bảo đảm đã xác minh" : serverMode === "demo" ? "Demo — dữ liệu minh họa" : "Demo / Live — theo cấu hình server"}</option>
                      <option value="research">Research Catalog — dữ liệu lịch sử (2023)</option>
                      <option disabled>{serverMode === "live" ? "Demo — cần đổi cấu hình server" : "Live — cần cấu hình và quyền truy cập nguồn"}</option>
                    </select>
                  </div>
                  {mode !== "research" ? (
                    <fieldset>
                      <legend className="field-label mb-1.5">Nguồn sàn hỗ trợ</legend>
                      <div className="flex h-10 items-center gap-4 text-xs font-medium">
                        {(["shopee", "lazada"] as const).map((source) => (
                          <label key={source} className="flex items-center gap-1.5 cursor-pointer">
                            <input type="checkbox" checked={sourcePlatforms.includes(source)} disabled={loading}
                              onChange={() => setSourcePlatforms((current) => current.includes(source) ? current.filter((item) => item !== source) : [...current, source])}
                              className="accent-[var(--brand)]" />
                            {source === "shopee" ? "Shopee" : "Lazada"}
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  ) : (
                    <div className="flex items-center"><p className="notice text-[11px] !p-2 !leading-relaxed">Chế độ Research: Sử dụng dataset sản phẩm lịch sử (2023) từ Amazon Reviews.</p></div>
                  )}
                </div>
                {mode !== "research" && (
                  <div className="mt-3 border-t border-[var(--line)] pt-3">
                    <label htmlFor="direct-product-url" className="field-label mb-1">URL sản phẩm trực tiếp (không bắt buộc)</label>
                    <input id="direct-product-url" type="url" value={directUrl} disabled={loading}
                      onChange={(event) => setDirectUrl(event.target.value)} className="field !h-10 !py-1.5 !text-xs"
                      placeholder="https://shopee.vn/... hoặc https://www.lazada.vn/..." />
                  </div>
                )}
              </div>

              {/* Submit CTA */}
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary mt-5 w-full !py-3.5 !text-sm font-semibold shadow-sm"
              >
                <Icon name="search" width="16" height="16" />
                <span>{loading ? "Đang xử lý nhu cầu…" : "Tìm bằng AI"}</span>
                <Icon name="arrow" width="16" height="16" className="ml-auto" />
              </button>

              <p className="muted mt-3 text-center text-[11px]">
                Nhấn <kbd className="rounded bg-[#e8efe9] px-1.5 py-0.5 font-mono text-[10px] text-[#244533]">Ctrl + Enter</kbd> để tìm kiếm nhanh · Không yêu cầu đăng nhập
              </p>
            </form>

            {/* Error banner */}
            {error && (
              <div role="alert" className="notice mt-4 !border-red-200 !bg-red-50 !text-red-900">
                <p className="font-semibold">{error}</p>
                <button
                  type="button"
                  className="text-link mt-2 text-xs !text-red-800 underline"
                  onClick={() => document.getElementById("shopping-query")?.focus()}
                >
                  Kiểm tra nhu cầu và thử lại
                </button>
              </div>
            )}

            {/* Loading progress */}
            {loading && (
              <div className="mt-4">
                <PipelineProgress phase={pipelinePhase} />
              </div>
            )}
          </div>

          {/* Prompt chips */}
          <section aria-label="Gợi ý nhu cầu" className="mx-auto mt-8 max-w-2xl">
            <div className="flex flex-col items-center gap-2 sm:flex-row sm:items-start sm:gap-3">
              <span className="muted shrink-0 pt-1.5 text-xs font-semibold">Gợi ý mẫu:</span>
              <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
                {examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    disabled={loading}
                    onClick={() => chooseExample(example)}
                    className="btn btn-secondary !min-h-[34px] !rounded-full !px-3.5 !py-1 !text-xs font-medium transition-all hover:!border-[var(--brand)] hover:!bg-[var(--brand-light)]"
                  >
                    <span>{example}</span>
                    <span aria-hidden="true" className="text-[var(--brand)] opacity-60">↗</span>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </div>
      </section>

      {/* Clarification Section */}
      {clarificationSessionId && clarificationQuestion && (
        <section aria-label="Bổ sung nhu cầu" className="page-container pt-10">
          <div className="surface mx-auto max-w-2xl border-[var(--brand)] p-6 sm:p-8 shadow-md">
            <span className="tag tag-green">
              Cần thêm thông tin · Câu hỏi {clarificationRound}
            </span>
            <h2 className="section-title mt-4 text-base sm:text-lg">
              {clarificationQuestion}
            </h2>
            <label htmlFor="clarification-answer" className="field-label mt-5">
              Câu trả lời của bạn
            </label>
            <textarea
              id="clarification-answer"
              autoFocus
              value={clarificationAnswer}
              onChange={(event) => {
                setClarificationAnswer(event.target.value);
                setError(null);
              }}
              onKeyDown={handleClarificationKeyDown}
              rows={3}
              disabled={loading}
              placeholder="Ví dụ: Tôi dùng chủ yếu để học online, họp trực tuyến và nghe nhạc hàng ngày..."
              className="field mt-2"
            />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="muted text-xs">
                Enter để tiếp tục · Shift + Enter để xuống dòng
              </p>
              <button
                type="button"
                disabled={loading || clarificationAnswer.trim().length < 2}
                onClick={() => void handleClarification()}
                className="btn btn-primary"
              >
                {loading ? "Đang xử lý…" : "Tiếp tục với AI →"}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* 3-Step Value Proposition */}
      <section id="how-it-works" className="page-container py-16 sm:py-20">
        <div className="mb-10 text-center sm:mb-12">
          <p className="eyebrow">Quy trình minh bạch & rõ ràng</p>
          <h2 className="mt-2.5 text-2xl font-bold tracking-tight sm:text-3xl text-[var(--foreground)]">
            Ít thời gian tìm kiếm. Nhiều cơ sở để lựa chọn.
          </h2>
          <p className="muted mx-auto mt-2 max-w-lg text-sm">
            Hệ thống hỗ trợ bạn từng bước từ lúc hình thành ý tưởng đến khi ra quyết định mua hàng.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {(
            [
              {
                icon: "search",
                title: "Nói điều bạn cần",
                text: "Ngân sách, mục đích sử dụng và những tiêu chí quan trọng. Bạn có thể mô tả hoàn toàn theo cách tự nhiên.",
              },
              {
                icon: "layers",
                title: "Khám phá các lựa chọn",
                text: "Hệ thống phân tích nhu cầu, tìm kiếm nguồn sản phẩm thực tế và đối chiếu từng tiêu chí theo dữ liệu thu thập.",
              },
              {
                icon: "shield",
                title: "Quyết định có cơ sở",
                text: "Xem điểm phù hợp, bằng chứng thực tế và những thông tin còn thiếu trước khi mở liên kết trang bán hàng.",
              },
            ] as const
          ).map((item, index) => (
            <div key={item.title} className="surface group p-6 sm:p-7 hover:border-[var(--line-strong)]">
              <div className="flex items-center justify-between">
                <span className="flex size-11 items-center justify-center rounded-xl bg-[var(--brand-light)] text-[var(--brand)] transition-transform duration-200 group-hover:scale-105">
                  <Icon name={item.icon} width="20" height="20" />
                </span>
                <span className="font-mono text-xs font-semibold text-[var(--muted)]">
                  0{index + 1}
                </span>
              </div>
              <h3 className="mt-5 text-base font-bold text-[var(--foreground)]">{item.title}</h3>
              <p className="muted mt-2 text-sm leading-relaxed">{item.text}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
