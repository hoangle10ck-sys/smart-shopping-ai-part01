import { Icon } from "./icon";

export function SiteFooter() {
  return <footer className="border-t border-[#dce4de] bg-white">
    <div className="page-container flex flex-col gap-5 py-8 sm:flex-row sm:items-center sm:justify-between">
      <div><p className="flex items-center gap-2 text-sm font-semibold"><Icon name="bag" /> Smart Shopping AI</p><p className="muted mt-2 text-xs">Hiểu nhu cầu. Tìm lựa chọn. Mua sắm có cơ sở.</p></div>
      <p className="muted text-xs">Đồ án ứng dụng AI trong hỗ trợ mua sắm.</p>
    </div>
  </footer>;
}
