import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Bell, X, CheckCheck, ChevronUp, ChevronDown } from 'lucide-react'

// Formata o horário da notificação de forma curta e legível
function horaCurta(v) {
  if (!v) return ''
  try {
    const d = new Date(String(v).replace(' ', 'T'))
    if (isNaN(d.getTime())) return String(v)
    return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return String(v) }
}

// Painel de notificações no canto superior direito. Fica visível até a pessoa
// marcar como lida (X individual) ou "Marcar todas". Altura limitada com rolagem
// interna para não cobrir a tela quando houver muitas.
export default function Notifications({ user }) {
  const [items, setItems] = useState([])
  const [min, setMin] = useState(true) // começa recolhido para não cobrir a tela

  async function load() {
    try { const r = await api.getNotificacoes(user.usuario); setItems(r.notificacoes || []) }
    catch { /* silencioso */ }
  }
  useEffect(() => {
    setItems([]); load()
    const t = setInterval(load, 12000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.usuario])

  async function dismiss(id) {
    setItems((xs) => xs.filter((n) => n.id !== id))
    try { await api.marcarLida(id) } catch { /* ignore */ }
  }
  async function dismissAll() {
    setItems([])
    try { await api.marcarTodasLidas(user.usuario) } catch { /* ignore */ }
  }

  if (!items.length) return null

  return (
    <>
      {/* Fundo escurecido quando aberto — destaca a mensagem */}
      {!min && <div className="fixed inset-0 z-[54] bg-black/55 backdrop-blur-[2px] no-print animate-fadeIn" onClick={() => setMin(true)} />}
      <div className="fixed bottom-4 right-4 z-[56] w-[380px] max-w-[calc(100vw-2rem)] no-print">
        <div className="card shadow-lift overflow-hidden flex flex-col max-h-[70vh]">
        {/* Cabeçalho fixo */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-line bg-surface-2/70 shrink-0">
          <div className="relative w-7 h-7 rounded-lg bg-brand/12 text-brand flex items-center justify-center shrink-0">
            <Bell className="w-4 h-4" />
            <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-brand text-brand-ink text-[10px] font-bold flex items-center justify-center">{items.length}</span>
          </div>
          <div className="flex-1 min-w-0 leading-none">
            <p className="text-[13px] font-semibold text-ink">Notificações</p>
            <p className="text-[11px] text-ink-faint mt-1">{items.length} {items.length === 1 ? 'não lida' : 'não lidas'}</p>
          </div>
          <button className="btn btn-ghost h-8 !px-2.5 text-[12px]" onClick={dismissAll} title="Marcar todas como lidas">
            <CheckCheck className="w-4 h-4" /> <span className="hidden sm:inline">Marcar todas</span>
          </button>
          <button className="icon-btn h-8 w-8" onClick={() => setMin((m) => !m)} title={min ? 'Expandir' : 'Minimizar'}>
            {min ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>

        {/* Lista rolável */}
        {!min && (
          <div className="overflow-y-auto divide-y divide-line">
            {items.map((n) => (
              <div key={n.id} className="p-3 flex items-start gap-2.5 hover:bg-surface-2/40 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-ink leading-snug break-words">{n.mensagem}</p>
                  {n.criado_em && <p className="text-[11px] text-ink-faint mt-1">{horaCurta(n.criado_em)}</p>}
                </div>
                <button className="icon-btn h-7 w-7 shrink-0" title="Marcar como lida" onClick={() => dismiss(n.id)}><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        )}
        </div>
      </div>
    </>
  )
}
