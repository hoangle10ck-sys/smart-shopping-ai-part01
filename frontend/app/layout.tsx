import type {
  Metadata,
} from "next";

import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: {
    default:
      "Smart Shopping AI - Trợ lý mua hàng thông minh",
    template:
      "%s | Smart Shopping AI",
  },
  description:
    "Hệ thống trợ lý mua hàng thông minh ứng dụng trí tuệ nhân tạo.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>
        <a href="#main-content" className="skip-link">Đến nội dung chính</a>
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
