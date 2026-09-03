import type { Metadata } from "next";
import "@fairhire/ui/tokens.css";
import "@fairhire/ui/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "FairHire AI", template: "%s · FairHire AI" },
  description: "Recruitment AI assurance and evidence workspace",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
