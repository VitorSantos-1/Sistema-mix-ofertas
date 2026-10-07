import { createContext, useCallback, useContext, useState } from 'react'
import { CheckCircle2, AlertTriangle, Info, X } from 'lucide-react'

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

let seq = 0
const ICONS = { success: CheckCircle2, error: AlertTriangle, info: Info }
const TONE = {
  success: 'border-good/40 bg-good/10 text-good',
  error: 'border-bad/40 bg-bad/10 text-bad',
  info: 'border-brand/40 bg-brand/10 text-brand',
}

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])

  const push = useCallback((msg, type = 'info', ttl = 4500) => {
    const id = ++seq
    setItems((xs) => [...xs, { id, msg, type }])
    if (ttl) setTimeout(() => setItems((xs) => xs.filter((t) => t.id !== id)), ttl)
  }, [])

  const dismiss = (id) => setItems((xs) => xs.filter((t) => t.id !== id))

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex w-[420px] max-w-[calc(100vw-2rem)] flex-col items-stretch gap-2 no-print">
        {items.map((t) => {
          const Icon = ICONS[t.type] || Info
          return (
            <div key={t.id} className={`card shadow-lift flex items-start gap-2 border px-3.5 py-3 text-sm animate-fadeIn ${TONE[t.type] || TONE.info}`}>
              <Icon size={18} className="mt-0.5 shrink-0" />
              <span className="flex-1 text-ink">{t.msg}</span>
              <button onClick={() => dismiss(t.id)} className="text-ink-faint hover:text-ink"><X size={16} /></button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}
