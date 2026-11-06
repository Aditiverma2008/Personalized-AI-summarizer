import "./globals.css";

export const metadata = {
  title: "Personalized Review Summarizer",
  description: "AI & NLP based review analysis tailored to your personal priorities.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
