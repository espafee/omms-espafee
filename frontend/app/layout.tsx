import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Outdoor Media Management",
  description: "Login portal for the outdoor media management system.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
