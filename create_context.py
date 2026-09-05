import os

os.makedirs('apps/terrapulse/frontend/src/contexts', exist_ok=True)

context_code = '''import React, { createContext, useContext, useState, ReactNode } from 'react';

export type RegionMode = 'sih-demo' | 'case-study';
export type RegionId = 'ner_india' | 'nepal_case';
export type DataStatus = 'simulation' | 'historical case';

interface RegionState {
  mode: RegionMode;
  region: RegionId;
  data_status: DataStatus;
}

interface RegionContextType {
  state: RegionState;
  setMode: (mode: RegionMode) => void;
}

const RegionContext = createContext<RegionContextType | undefined>(undefined);

export const RegionProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<RegionState>({
    mode: 'sih-demo',
    region: 'ner_india',
    data_status: 'simulation'
  });

  const setMode = (mode: RegionMode) => {
    if (mode === 'sih-demo') {
      setState({
        mode: 'sih-demo',
        region: 'ner_india',
        data_status: 'simulation'
      });
    } else {
      setState({
        mode: 'case-study',
        region: 'nepal_case',
        data_status: 'historical case'
      });
    }
  };

  return (
    <RegionContext.Provider value={{ state, setMode }}>
      {children}
    </RegionContext.Provider>
  );
};

export const useRegion = () => {
  const context = useContext(RegionContext);
  if (context === undefined) {
    throw new Error('useRegion must be used within a RegionProvider');
  }
  return context;
};
'''

with open('apps/terrapulse/frontend/src/contexts/RegionContext.tsx', 'w', encoding='utf-8') as f:
    f.write(context_code)
