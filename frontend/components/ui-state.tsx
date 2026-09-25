import Link from "next/link";
import { Icon } from "./icon";

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="surface px-6 py-14 text-center"><span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[#eef3eb] text-[#165b46]"><Icon name="search" width="26" height="26" /></span><h2 className="section-title mt-5">{title}</h2><p className="muted mx-auto mt-3 max-w-md text-sm leading-6">{description}</p><div className="mt-6">{action ?? <Link href="/" className="btn btn-primary">Tìm kiếm mới <Icon name="arrow" /></Link>}</div></div>;
}
export function ErrorState({ title, retry }: { title: string; retry?: () => void }) {
  return <div role="alert" className="surface p-8 text-center"><span className="tag tag-amber">Kết nối cần được kiểm tra</span><h2 className="section-title mt-4">{title}</h2><p className="muted mt-3 text-sm">Vui lòng thử lại sau ít phút hoặc bắt đầu một tìm kiếm mới.</p><div className="mt-6 flex flex-wrap justify-center gap-3">{retry && <button type="button" className="btn btn-primary" onClick={retry}>Thử lại</button>}<Link href="/" className="btn btn-secondary">Tìm kiếm mới</Link></div></div>;
}
