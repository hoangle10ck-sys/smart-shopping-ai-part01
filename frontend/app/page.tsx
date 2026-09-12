"use client";

import {
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import { PipelineProgress } from "@/components/pipeline-progress";

import {
  SiteHeader,
} from "@/components/site-header";

import {
  analyzeRequirement,
  clarifyRequirement,
  executeSearch,
} from "@/lib/api";


const examples = [
  "Laptop khoảng 20 triệu để học lập trình",
  "Tai nghe dưới 500 nghìn, mic tốt, pin lâu",
  "Điện thoại khoảng 10 triệu, camera đẹp",
];


export default function Home() {
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
        caught instanceof Error
          ? caught.message
          : "Không thể kết nối với hệ thống AI.",
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
        caught instanceof Error
          ? caught.message
          : "Không thể gửi thông tin bổ sung.",
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


    window.location.href =
      `/results/${searchResult.session_id}`;
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
    <main className="min-h-screen">
      <SiteHeader />


      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute -left-32 top-12 h-96 w-96 rounded-full bg-blue-400/15 blur-3xl" />

          <div className="absolute right-0 top-20 h-96 w-96 rounded-full bg-violet-400/15 blur-3xl" />
        </div>


        <div className="mx-auto max-w-7xl px-5 pb-24 pt-24 text-center lg:px-8 lg:pt-32">
          {/* BADGE */}
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-bold text-blue-700">
            ✨ AI Shopping Assistant

            <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] text-white">
              BETA
            </span>
          </div>


          {/* TITLE */}
          <h1 className="mx-auto max-w-4xl text-5xl font-black leading-[1.08] tracking-tight text-slate-950 sm:text-6xl lg:text-7xl">
            Tìm sản phẩm phù hợp

            <span className="block bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 bg-clip-text text-transparent">
              bằng trí tuệ nhân tạo
            </span>
          </h1>


          {/* DESCRIPTION */}
          <p className="mx-auto mt-7 max-w-2xl text-lg leading-8 text-slate-500">
            Chỉ cần mô tả nhu cầu của bạn.
            Smart Shopping AI sẽ phân tích,
            tìm kiếm, đánh giá và xếp hạng
            sản phẩm phù hợp nhất.
          </p>


          {/* SEARCH FORM */}
          <form
            onSubmit={
              handleSubmit
            }
            className="mx-auto mt-10 max-w-3xl"
          >
            <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-2xl shadow-blue-950/10">
              <textarea
                value={query}
                onChange={(
                  event,
                ) => {
                  setQuery(
                    event
                      .target
                      .value,
                  );

                  if (error) {
                    setError(
                      null,
                    );
                  }
                }}
                rows={3}
                disabled={
                  loading
                }
                placeholder="Ví dụ: Tôi cần laptop khoảng 20 triệu để học lập trình, RAM 16GB, pin tốt..."
                className="w-full resize-none rounded-2xl border-0 bg-transparent px-4 py-4 text-base leading-7 text-slate-900 outline-none placeholder:text-slate-400"
              />


              <div className="flex flex-col gap-3 border-t border-slate-100 px-2 pt-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-left text-xs font-medium text-slate-400">
                  🔒 AI chỉ sử dụng thông tin
                  để tìm sản phẩm phù hợp.
                </div>


                <button
                  type="submit"
                  disabled={
                    loading
                  }
                  className="inline-flex min-w-40 items-center justify-center rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3.5 text-sm font-extrabold text-white shadow-lg shadow-blue-500/25 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading
                    ? "Đang chờ backend..."
                    : "✨ Tìm bằng AI"}
                </button>
              </div>
            </div>
          </form>


          {loading && <div className="mx-auto mt-5 max-w-3xl"><PipelineProgress phase={pipelinePhase} /></div>}

          {/* ERROR */}
          {error && (
            <div className="mx-auto mt-4 max-w-3xl rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-left text-sm font-semibold text-red-700">
              {error}
            </div>
          )}


          {/* CLARIFICATION */}
          {clarificationSessionId &&
            clarificationQuestion && (
              <div className="mx-auto mt-6 max-w-3xl overflow-hidden rounded-[28px] border border-blue-200 bg-white text-left shadow-xl shadow-blue-950/5">
                {/* HEADER */}
                <div className="border-b border-blue-100 bg-gradient-to-r from-blue-50 to-indigo-50 px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600 text-xl shadow-sm">
                      🤖
                    </div>


                    <div>
                      <div className="font-extrabold text-slate-950">
                        Smart Shopping AI
                      </div>

                      <div className="mt-0.5 text-xs font-semibold text-blue-600">
                        Cần thêm thông tin
                        {clarificationRound >
                          0
                          ? ` • Câu hỏi ${clarificationRound}`
                          : ""}
                      </div>
                    </div>
                  </div>
                </div>


                {/* BODY */}
                <div className="p-5">
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-sm font-bold leading-7 text-slate-800">
                      {
                        clarificationQuestion
                      }
                    </p>
                  </div>


                  <div className="mt-4">
                    <label className="mb-2 block text-xs font-extrabold uppercase tracking-wide text-slate-500">
                      Câu trả lời của bạn
                    </label>


                    <textarea
                      value={
                        clarificationAnswer
                      }
                      onChange={(
                        event,
                      ) => {
                        setClarificationAnswer(
                          event
                            .target
                            .value,
                        );

                        if (
                          error
                        ) {
                          setError(
                            null,
                          );
                        }
                      }}
                      onKeyDown={
                        handleClarificationKeyDown
                      }
                      rows={3}
                      disabled={
                        loading
                      }
                      autoFocus
                      placeholder="Ví dụ: Tôi dùng chủ yếu để học online và họp trực tuyến..."
                      className="w-full resize-none rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                    />
                  </div>


                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs text-slate-400">
                      Nhấn Enter để tiếp tục,
                      Shift + Enter để xuống dòng.
                    </p>


                    <button
                      type="button"
                      disabled={
                        loading ||
                        clarificationAnswer
                          .trim()
                          .length <
                          2
                      }
                      onClick={() =>
                        void handleClarification()
                      }
                      className="inline-flex items-center justify-center rounded-2xl bg-blue-600 px-5 py-3 text-sm font-extrabold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {loading
                        ? "AI đang xử lý..."
                        : "Tiếp tục với AI →"}
                    </button>
                  </div>
                </div>
              </div>
            )}


          {/* EXAMPLES */}
          <div className="mx-auto mt-7 flex max-w-3xl flex-wrap justify-center gap-2">
            <span className="py-2 text-xs font-bold text-slate-400">
              Thử nhanh:
            </span>


            {examples.map(
              (
                example,
              ) => (
                <button
                  key={
                    example
                  }
                  type="button"
                  disabled={
                    loading
                  }
                  onClick={() =>
                    chooseExample(
                      example,
                    )
                  }
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {example}
                </button>
              ),
            )}
          </div>
        </div>
      </section>


      {/* HOW IT WORKS */}
      <section
        id="how-it-works"
        className="border-y border-slate-200 bg-white"
      >
        <div className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
          <div className="mb-12 text-center">
            <p className="text-sm font-extrabold uppercase tracking-[0.25em] text-blue-600">
              Quy trình AI
            </p>


            <h2 className="mt-3 text-3xl font-black text-slate-950">
              Mua sắm thông minh trong
              3 bước
            </h2>
          </div>


          <div className="grid gap-5 md:grid-cols-3">
            {[
              {
                icon: "💬",

                title:
                  "1. Mô tả nhu cầu",

                text:
                  "Nhập ngân sách, mục đích và điều bạn quan tâm bằng ngôn ngữ tự nhiên.",
              },

              {
                icon: "🧠",

                title:
                  "2. AI phân tích",

                text:
                  "Nếu thông tin chưa đủ, AI sẽ hỏi thêm trước khi tìm kiếm và chấm điểm sản phẩm.",
              },

              {
                icon: "🏆",

                title:
                  "3. Nhận đề xuất",

                text:
                  "Xem AI Match, độ tin cậy, giá, rating và lý do sản phẩm phù hợp.",
              },
            ].map(
              (item) => (
                <article
                  key={
                    item.title
                  }
                  className="rounded-[28px] border border-slate-200 bg-slate-50 p-7"
                >
                  <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-2xl shadow-sm">
                    {
                      item.icon
                    }
                  </div>


                  <h3 className="text-lg font-extrabold text-slate-950">
                    {
                      item.title
                    }
                  </h3>


                  <p className="mt-3 leading-7 text-slate-500">
                    {
                      item.text
                    }
                  </p>
                </article>
              ),
            )}
          </div>
        </div>
      </section>
    </main>
  );
}