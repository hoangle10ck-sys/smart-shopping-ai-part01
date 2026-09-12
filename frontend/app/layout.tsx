import type {
  Metadata,
} from "next";

import "./globals.css";

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
        {children}
      </body>
    </html>
  );
}