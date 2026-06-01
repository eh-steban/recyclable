import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recyclable -- Denver Recycling Guide",
  description: "Grounded, source-cited recycling rules for Denver, CO.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
