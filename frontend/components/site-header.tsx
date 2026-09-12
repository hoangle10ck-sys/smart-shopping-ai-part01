import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl">
      <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-5 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-3"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-violet-600 text-lg font-black text-white shadow-lg shadow-blue-500/20">
            AI
          </div>

          <div>
            <div className="text-lg font-extrabold tracking-tight text-slate-950">
              Smart Shopping
              <span className="text-blue-600">
                {" "}AI 
              </span>
            </div>

            <div className="hidden text-[11px] font-medium text-slate-400 sm:block">
              Trợ lý mua hàng thông minh
            </div>
          </div>
        </Link>

        <nav className="flex items-center gap-1">
          <Link
            href="/"
            className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
          >
            Trang chủ
          </Link>

          <a
            href="/#how-it-works"
            className="hidden rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 sm:block"
          >
            Cách hoạt động
          </a>

          <div className="ml-2 hidden rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700 md:block">
            ● AI Online
          </div>
        </nav>
      </div>
    </header>
  );
}