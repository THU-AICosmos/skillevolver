import type { Metadata } from 'next';
import { AppearanceProvider } from '@/components/AppearanceProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'TechPulse Blog',
  description: 'Stay ahead with the latest in tech',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AppearanceProvider>
          {children}
        </AppearanceProvider>
      </body>
    </html>
  );
}
