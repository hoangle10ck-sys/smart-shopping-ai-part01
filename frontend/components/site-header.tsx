"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icon";

export function SiteHeader() {
  const pathname = usePathname();
  return <header className="sticky top-0 z-40 border-b border-[#dce4de] bg-white/95 backdrop-blur-md">
    <div className="page-container flex min-h-17 items-center justify-between gap-3">
      <Link href="/" aria-label="Smart Shopping AI — Trang chủ" className="flex min-w-0 items-center gap-2.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#165b46] text-white"><Icon name="bag" /></span>
        <span className="text-sm font-bold tracking-tight sm:text-base">Smart Shopping <span className="text-[#287452]">AI</span></span>
      </Link>
      <nav aria-label="Điều hướng chính" className="flex shrink-0 items-center gap-1 text-xs sm:gap-2 sm:text-sm">
        {[['/', 'Trang chủ'], ['/history', 'Lịch sử']].map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined} className={`rounded-lg px-2.5 py-3 font-semibold transition sm:px-4 ${pathname === href ? 'bg-[#eef4ed] text-[#165b46]' : 'muted hover:bg-[#f3f5f1]'}`}>{label}</Link>)}
      </nav>
    </div>
  </header>;
}
