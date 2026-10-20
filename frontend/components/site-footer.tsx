import { Icon } from "./icon";

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--line)] bg-white text-xs">
      <div className="page-container flex flex-col gap-6 py-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
            <span className="flex size-6 items-center justify-center rounded-lg bg-[var(--brand)] text-white">
              <Icon name="bag" width="13" height="13" />
            </span>
            Smart Shopping AI
          </p>
          <p className="muted mt-1.5 leading-5 text-[12px]">
            Hệ thống trợ lý tìm kiếm sản phẩm & đối chiếu giá minh bạch theo nhu cầu thực tế.
          </p>
        </div>
        <div className="flex flex-col gap-1 sm:items-end">
          <p className="muted text-[11.5px]">
            Dữ liệu đối chiếu từ nguồn thu thập công khai. Không can thiệp xếp hạng hay giá gốc.
          </p>
          <p className="muted text-[11px] opacity-80">
            Hỗ trợ tìm kiếm & đối chiếu trực tiếp không cần đăng nhập.
          </p>
        </div>
      </div>
    </footer>
  );
}
