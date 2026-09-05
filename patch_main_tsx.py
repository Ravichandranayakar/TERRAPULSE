content = '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { RegionProvider } from './contexts/RegionContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RegionProvider>
      <App />
    </RegionProvider>
  </React.StrictMode>,
)'''
with open('apps/terrapulse/frontend/src/main.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
