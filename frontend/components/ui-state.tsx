import Link from "next/link";
import { Icon } from "./icon";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="surface px-6 py-14 text-center">
      <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[var(--brand-light)] text-[var(--brand)] shadow-xs">
        <Icon name="search" width="26" height="26" />
      </span>
      <h2 className="section-title mt-5 text-base sm:text-lg">{title}</h2>
      <p className="muted mx-auto mt-2.5 max-w-md text-xs sm:text-sm leading-relaxed">
        {description}
      </p>
      <div className="mt-6">
        {action ?? (
          <Link href="/" className="btn btn-primary">
            <span>Tìm kiếm mới</span>
            <Icon name="arrow" width="16" height="16" />
          </Link>
        )}
      </div>
    </div>
  );
}

export function ErrorState({
  title,
  retry,
}: {
  title: string;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="surface p-8 text-center border-amber-200 bg-amber-50/40">
      <span className="tag tag-amber font-semibold">Kết nối cần được kiểm tra</span>
      <h2 className="section-title mt-4 text-base sm:text-lg">{title}</h2>
      <p className="muted mx-auto mt-2.5 max-w-md text-xs sm:text-sm leading-relaxed">
        Vui lòng thử lại sau ít phút hoặc bắt đầu một tìm kiếm mới.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {retry && (
          <button type="button" className="btn btn-primary" onClick={retry}>
            Thử lại
          </button>
        )}
        <Link href="/" className="btn btn-secondary">
          Tìm kiếm mới
        </Link>
      </div>
    </div>
  );
}
