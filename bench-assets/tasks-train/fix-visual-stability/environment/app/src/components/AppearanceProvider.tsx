'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Mode = 'day' | 'night';

const AppearanceContext = createContext<{
  mode: Mode;
  cycleMode: () => void;
}>({ mode: 'day', cycleMode: () => {} });

export function useAppearance() {
  return useContext(AppearanceContext);
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>('day');

  useEffect(() => {
    const stored = localStorage.getItem('appearance') as Mode;
    if (stored) {
      setMode(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode);
  }, [mode]);

  const cycleMode = () => {
    const next = mode === 'day' ? 'night' : 'day';
    setMode(next);
    localStorage.setItem('appearance', next);
  };

  return (
    <AppearanceContext.Provider value={{ mode, cycleMode }}>
      <div data-testid="appearance-shell" id="appearance-shell" className={`min-h-screen ${mode === 'night' ? 'bg-[#1e1e2e] text-[#e0e0e0]' : 'bg-[#fafafa] text-[#1a1a2e]'}`}>
        {children}
      </div>
    </AppearanceContext.Provider>
  );
}
