import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'ReadSlow - News Reader',
  description: 'A definitely-not-slow reading experience',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
