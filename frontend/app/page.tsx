"use client";

import {
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import { PipelineProgress } from "@/components/pipeline-progress";

import { Icon } from "@/components/icon";
import { useRouter } from "next/navigation";

import {
  analyzeRequirement,
  clarifyRequirement,
  executeSearch,
} from "@/lib/api";


const examples = [
  "Điện thoại khoảng 10 triệu, camera tốt, pin lâu",
  "Laptop khoảng 20 triệu để học lập trình",
  "TV khoảng 10 triệu để xem phim",
  "Xe máy khoảng 33 triệu để đi học",
];


export default function Home() {
  const router = useRouter();
  const [pipelinePhase, setPipelinePhase] = useState<"analyze" | "search">("analyze");
  const [
    query,
    setQuery,
  ] = useState("");


  const [
    loading,
    setLoading,
  ] = useState(false);


  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );


  /*
   * Clarification state
   */
  const [
    clarificationSessionId,
    setClarificationSessionId,
  ] =
    useState<string | null>(
      null,
    );


  const [
    clarificationQuestion,
    setClarificationQuestion,
  ] =
    useState<string | null>(
      null,
    );


  const [
    clarificationAnswer,
    setClarificationAnswer,
  ] =
    useState("");


  const [
    clarificationRound,
    setClarificationRound,
  ] =
    useState(0);


  /*
   * SEARCH MỚI
   */
  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();


    const value =
      query.trim();


    if (
      value.length < 5
    ) {
      setError(
        "Hãy mô tả nhu cầu chi tiết hơn một chút.",
      );

      return;
    }


    /*
     * Reset clarification cũ
     */
    setClarificationSessionId(
      null,
    );

    setClarificationQuestion(
      null,
    );

    setClarificationAnswer(
      "",
    );

    setClarificationRound(
      0,
    );


    setError(null);
    setLoading(true);
    setPipelinePhase("analyze");


    try {
      console.log(
        "[Smart Shopping] Analyze:",
        value,
      );


      const analyzed =
        await analyzeRequirement(
          value,
        );


      console.log(
        "[Smart Shopping] Analyze response:",
        analyzed,
      );


      if (
        !analyzed.session_id
      ) {
        throw new Error(
          "Backend không trả về session_id.",
        );
      }


      /*
       * AI thiếu thông tin
       */
      if (
        analyzed.needs_clarification
      ) {
        setClarificationSessionId(
          analyzed.session_id,
        );


        setClarificationQuestion(
          analyzed
            .clarification_question ??
            "Bạn có thể bổ sung thêm mục đích sử dụng, ngân sách hoặc yêu cầu quan trọng không?",
        );


        setClarificationRound(
          1,
        );


        return;
      }


      /*
       * Đủ thông tin
       * → chạy search
       */
      await runSearch(
        analyzed.session_id,
      );
    } catch (caught) {
      console.error(
        "[Smart Shopping] Error:",
        caught,
      );


      setError(
        "Chưa thể kết nối để tìm kiếm. Vui lòng thử lại sau ít phút.",
      );
    } finally {
      setLoading(false);
    }
  }


  /*
   * GỬI CÂU TRẢ LỜI CHO AI
   */
  async function handleClarification() {
    const answer =
      clarificationAnswer.trim();


    if (
      !clarificationSessionId
    ) {
      setError(
        "Phiên phân tích không hợp lệ.",
      );

      return;
    }


    if (
      answer.length < 2
    ) {
      setError(
        "Hãy nhập thêm thông tin để AI tiếp tục phân tích.",
      );

      return;
    }


    setError(null);
    setLoading(true);
    setPipelinePhase("analyze");


    try {
      console.log(
        "[Smart Shopping] Clarification:",
        {
          sessionId:
            clarificationSessionId,

          answer,
        },
      );


      const clarified =
        await clarifyRequirement(
          clarificationSessionId,
          answer,
        );


      console.log(
        "[Smart Shopping] Clarification response:",
        clarified,
      );


      if (
        !clarified.session_id
      ) {
        throw new Error(
          "Backend không trả về session_id sau khi làm rõ.",
        );
      }


      /*
       * Nếu AI vẫn thiếu thông tin
       * thì tiếp tục hỏi
       */
      if (
        clarified.needs_clarification
      ) {
        setClarificationSessionId(
          clarified.session_id,
        );


        setClarificationQuestion(
          clarified
            .clarification_question ??
            "AI vẫn cần thêm một chút thông tin. Bạn có thể mô tả rõ hơn không?",
        );


        setClarificationAnswer(
          "",
        );


        setClarificationRound(
          (
            current,
          ) =>
            current + 1,
        );


        return;
      }


      /*
       * Đã đủ thông tin
       */
      setClarificationSessionId(
        null,
      );

      setClarificationQuestion(
        null,
      );

      setClarificationAnswer(
        "",
      );


      /*
       * Chạy search
       */
      await runSearch(
        clarified.session_id,
      );
    } catch (caught) {
      console.error(
        "[Smart Shopping] Clarification error:",
        caught,
      );


      setError(
        "Chưa gửi được thông tin bổ sung. Vui lòng thử lại.",
      );
    } finally {
      setLoading(false);
    }
  }


  /*
   * SEARCH PIPELINE
   */
  async function runSearch(
    sessionId: string,
  ) {
    console.log(
      "[Smart Shopping] Execute Search:",
      sessionId,
    );


    setPipelinePhase("search");
    const searchResult =
      await executeSearch(
        sessionId,
      );


    console.log(
      "[Smart Shopping] Search result:",
      searchResult,
    );


    if (
      !searchResult.session_id
    ) {
      throw new Error(
        "Backend không trả về session_id sau khi tìm kiếm.",
      );
    }


    router.push(`/results/${searchResult.session_id}`);
  }


  /*
   * Cho phép nhấn Enter trong
   * clarification textarea.
   */
  function handleClarificationKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key ===
        "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (!loading) {
        void handleClarification();
      }
    }
  }


  function chooseExample(
    example: string,
  ) {
    setQuery(example);

    setError(null);

    setClarificationSessionId(
      null,
    );

    setClarificationQuestion(
      null,
    );

    setClarificationAnswer(
      "",
    );

    setClarificationRound(
      0,
    );
  }


  return (
    <main id="main-content" tabIndex={-1}>
      <section className="relative border-b border-[#dce4de] bg-[#f6f7f0]">
        <div className="page-container grid gap-10 py-12 lg:grid-cols-[.95fr_1.05fr] lg:items-center lg:gap-16 lg:py-22">
          <div>
            <p className="eyebrow flex items-center gap-2"><Icon name="spark" width="16" height="16" /> Trợ lý mua sắm của bạn</p>
            <h1 className="mt-6 max-w-xl text-[clamp(2.5rem,4.5vw,4.2rem)] leading-[1.13] font-semibold tracking-[-.045em]">
              Mua sắm thông minh hơn.<br /><span className="text-[#287452]">Bắt đầu từ nhu cầu.</span>
            </h1>
            <p className="muted mt-6 max-w-md text-base leading-7">Mô tả điều bạn đang tìm. Smart Shopping AI tìm kiếm, đánh giá và đề xuất sản phẩm từ các nguồn trên web để bạn có thêm cơ sở lựa chọn.</p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-xs font-medium text-[#526a58]">
              <span className="flex items-center gap-2"><Icon name="globe" width="16" height="16" /> Nguồn thông tin rõ ràng</span>
              <span className="flex items-center gap-2"><Icon name="layers" width="16" height="16" /> So sánh theo nhu cầu</span>
            </div>
          </div>
          <div className="min-w-0">
            <form onSubmit={handleSubmit} className="surface overflow-hidden !rounded-3xl !border-[#cddbc9] p-5 shadow-[0_16px_50px_-24px_#244a3040] sm:p-7" aria-busy={loading}>
              <div className="mb-5 flex items-center justify-between gap-3"><label htmlFor="shopping-query" className="font-semibold">Bạn đang tìm sản phẩm gì?</label><Icon name="spark" className="text-[#287452]" /></div>
              <textarea id="shopping-query" value={query} onChange={event => { setQuery(event.target.value); setError(null); }} rows={5} disabled={loading}
                onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); if (!loading) event.currentTarget.form?.requestSubmit(); } }}
                placeholder="Ví dụ: Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu..."
                aria-describedby="search-hint" aria-invalid={!!error}
                className="field resize-y !rounded-xl !border-[#e0e7dc] !bg-[#f8faf6] !p-4 !text-base leading-7" />
              <p id="search-hint" className="muted mt-3 text-xs">Thêm ngân sách, mục đích và tiêu chí bạn quan tâm.</p>
              <button type="submit" disabled={loading} className="btn btn-primary mt-5 w-full !py-3.5 !text-sm"><Icon name="search" />{loading ? 'Đang xử lý nhu cầu…' : 'Tìm bằng AI'}<Icon name="arrow" className="ml-auto" /></button>
              <p className="muted mt-3 text-center text-[11px]">Ctrl + Enter để tìm kiếm · Không cần biết trước tên sản phẩm</p>
            </form>
            {error && <div role="alert" className="notice mt-4"><p>{error}</p><button type="button" className="text-link mt-2" onClick={() => document.getElementById('shopping-query')?.focus()}>Kiểm tra nhu cầu và thử lại</button></div>}
            {loading && <div className="mt-4"><PipelineProgress phase={pipelinePhase} /></div>}
          </div>
        </div>
      </section>

      {clarificationSessionId && clarificationQuestion && <section aria-label="Bổ sung nhu cầu" className="page-container pt-8">
        <div className="surface mx-auto max-w-3xl p-6 sm:p-8">
          <span className="tag tag-green">Cần thêm thông tin · Câu hỏi {clarificationRound}</span>
          <h2 className="section-title mt-4">{clarificationQuestion}</h2>
          <label htmlFor="clarification-answer" className="field-label mt-5">Câu trả lời của bạn</label>
          <textarea id="clarification-answer" autoFocus value={clarificationAnswer} onChange={event => { setClarificationAnswer(event.target.value); setError(null); }} onKeyDown={handleClarificationKeyDown} rows={3} disabled={loading} placeholder="Ví dụ: Tôi dùng chủ yếu để học online và họp trực tuyến..." className="field mt-2" />
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p className="muted text-xs">Enter để tiếp tục · Shift + Enter để xuống dòng</p><button type="button" disabled={loading || clarificationAnswer.trim().length < 2} onClick={() => void handleClarification()} className="btn btn-primary">{loading ? 'Đang xử lý…' : 'Tiếp tục với AI →'}</button></div>
        </div>
      </section>}

      <section aria-label="Gợi ý nhu cầu" className="page-container py-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
          <p className="muted shrink-0 pt-2 text-xs font-semibold">Bắt đầu với một gợi ý</p>
          <div className="flex flex-wrap gap-2">{examples.map(example => <button key={example} type="button" disabled={loading} onClick={() => chooseExample(example)} className="btn btn-secondary !rounded-full !px-4 !py-2 !text-xs">{example}<span aria-hidden="true" className="text-[#6b816e]">↗</span></button>)}</div>
        </div>
      </section>

      <section id="how-it-works" className="page-container pb-18 pt-8">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">Từ ý tưởng đến lựa chọn</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">Ít thời gian tìm. Nhiều cơ sở chọn.</h2></div><span className="muted text-sm">Một quy trình rõ ràng trong 3 bước</span></div>
        <div className="grid gap-4 md:grid-cols-3">
          {([
            {icon:'search', title:'Nói điều bạn cần', text:'Ngân sách, mục đích sử dụng và những tiêu chí quan trọng. Mô tả theo cách của bạn.'},
            {icon:'layers', title:'Khám phá các lựa chọn', text:'Hệ thống phân tích nhu cầu, tìm nguồn và đối chiếu thông tin sản phẩm.'},
            {icon:'shield', title:'Quyết định có cơ sở', text:'Xem điểm phù hợp, bằng chứng và thông tin còn thiếu trước khi mở trang bán.'},
          ] as const).map((item, index) => <div key={item.title} className="surface p-6"><div className="flex items-center justify-between"><span className="rounded-xl bg-[#edf3e9] p-3 text-[#286543]"><Icon name={item.icon} /></span><span className="text-sm text-[#69756d]">0{index+1}</span></div><h3 className="mt-5 font-semibold">{item.title}</h3><p className="muted mt-2 text-sm leading-6">{item.text}</p></div>)}
        </div>
      </section>
    </main>
  );
}
