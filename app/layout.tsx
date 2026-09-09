import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Города во времени — живой атлас',
  description:
    'Исследуйте появление и рост городов на интерактивной исторической карте.',
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
