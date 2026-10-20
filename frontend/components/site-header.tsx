"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icon";

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-white/95 backdrop-blur-md transition-shadow">
      <div className="page-container flex min-h-[64px] items-center justify-between gap-4">
        <Link
          href="/"
          aria-label="Smart Shopping AI — Trang chủ"
          className="group flex min-w-0 items-center gap-2.5 transition-opacity hover:opacity-90"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[var(--brand)] text-white shadow-sm transition-transform duration-200 group-hover:scale-105">
            <Icon name="bag" width="18" height="18" />
          </span>
          <span className="text-sm font-bold tracking-tight sm:text-base text-[var(--foreground)]">
            Smart Shopping <span className="text-[var(--brand)]">AI</span>
          </span>
        </Link>

        <nav aria-label="Điều hướng chính" className="flex shrink-0 items-center gap-1 sm:gap-1.5 text-xs sm:text-sm">
          {[
            ["/", "Trang chủ"],
            ["/history", "Lịch sử"],
          ].map(([href, label]) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={`rounded-lg px-3 py-2 font-semibold transition-all duration-150 sm:px-4 ${
                  isActive
                    ? "bg-[var(--brand-light)] text-[var(--brand)] shadow-xs"
                    : "text-[var(--muted)] hover:bg-[var(--surface-subtle)] hover:text-[var(--foreground)]"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
