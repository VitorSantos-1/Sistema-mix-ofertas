import React from 'react'
import { createRoot } from 'react-dom/client'
import './original.css'   // CSS EXATO do app original (design fiel — base + componentes)
import './tw-utils.css'   // utilitários Tailwind (só utilities; cores pelos mesmos tokens)
import './extra.css'      // acréscimos mínimos (impressão + nome sem corte)
import App from './App.jsx'

// aplica o tema salvo já no carregamento (inclusive na tela de login)
try { if (localStorage.getItem('theme') === 'dark') document.documentElement.classList.add('dark') } catch { /* ignore */ }

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
