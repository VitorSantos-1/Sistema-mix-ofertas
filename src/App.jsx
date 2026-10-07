import { useState, useEffect } from 'react'
import { getAuthUser } from './lib/api'
import { ToastProvider } from './lib/toast'
import Login from './screens/Login'
import Campaigns from './screens/Campaigns'
import Editor from './screens/Editor'
import Catalogo from './screens/Catalogo'
import Parametros from './screens/Parametros'
import Equipe from './screens/Equipe'
import Notifications from './components/Notifications'
import { Store, Layers, Database, SlidersHorizontal, Users, Plus, Sun, Moon, LogOut } from 'lucide-react'

function Shell() {
  const [user, setUser] = useState(getAuthUser())
  const [view, setView] = useState({ name: 'dashboard' })
  const [novaCampanha, setNovaCampanha] = useState(false) // sinal p/ abrir modal na tela de campanhas (consumível)
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem('theme') || 'light' } catch { return 'light' } })

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') root.classList.add('dark'); else root.classList.remove('dark')
    try { localStorage.setItem('theme', theme) } catch { /* ignore */ }
  }, [theme])
  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  if (!user) return <Login onLogin={(u) => setUser(u)} />

  const isAdm = user.role === 'adm'
  const go = (name, params = {}) => setView({ name, ...params })
  const logout = () => {
    localStorage.removeItem('auth_user'); localStorage.removeItem('auth_token'); localStorage.removeItem('op_name')
    setUser(null); setView({ name: 'dashboard' })
  }

  const nav = [
    { id: 'dashboard', label: 'Campanhas', Icon: Layers, show: true },
    { id: 'catalogo', label: 'Catálogo', Icon: Database, show: isAdm },
    { id: 'parametros', label: 'Parâmetros', Icon: SlidersHorizontal, show: isAdm },
    { id: 'equipe', label: 'Equipe', Icon: Users, show: isAdm },
  ].filter((n) => n.show)
  const activeNav = view.name === 'editor' ? 'dashboard' : view.name
  const inicial = (user.nome || user.usuario || '?').trim().charAt(0).toUpperCase()

  return (
    <div className="min-h-screen bg-bg text-ink flex flex-col">
      <header className="sticky top-0 z-40 w-full border-b border-line bg-surface/85 backdrop-blur-md no-print">
        <div className="max-w-app mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            <button className="flex items-center gap-3 shrink-0" onClick={() => go('dashboard')}>
              <div className="w-9 h-9 rounded-xl bg-brand text-brand-ink flex items-center justify-center shadow-soft">
                <Store className="w-[18px] h-[18px]" />
              </div>
              <div className="text-left leading-none hidden xs:block">
                <div className="font-display text-[15px] font-bold tracking-tight text-ink">Opção<span className="text-ink-faint font-medium"> · Ofertas</span></div>
                <div className="text-[11px] text-ink-faint mt-1">Mix &amp; Encartes</div>
              </div>
            </button>

            <nav className="seg hidden md:flex">
              {nav.map((n) => (
                <button key={n.id} data-active={activeNav === n.id} className="seg-item" onClick={() => go(n.id)}>
                  <n.Icon className="w-4 h-4" /><span>{n.label}</span>
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-2 shrink-0">
              <div className="hidden sm:flex items-center gap-2.5 pl-1 pr-3 py-1 rounded-xl">
                <div className="relative w-8 h-8 rounded-lg bg-surface-2 border border-line text-ink flex items-center justify-center text-xs font-bold font-display">
                  {inicial}
                  <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-brand border-2 border-surface" title={user.cargo || ''}></span>
                </div>
                <div className="leading-none">
                  <p className="text-[13px] font-semibold text-ink">{user.nome || user.usuario}</p>
                  <p className="text-[11px] text-ink-faint mt-1">{user.cargo || user.role}</p>
                </div>
              </div>
              {isAdm && (
                <button className="btn btn-primary" onClick={() => { go('dashboard'); setNovaCampanha(true) }}>
                  <Plus className="w-4 h-4" /><span className="hidden sm:inline">Nova campanha</span>
                </button>
              )}
              <button className="icon-btn" title={theme === 'dark' ? 'Tema claro' : 'Tema escuro'} onClick={toggleTheme}>
                {theme === 'dark' ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
              </button>
              <button className="icon-btn" title="Sair" onClick={logout}><LogOut className="w-[18px] h-[18px]" /></button>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-app w-full mx-auto px-4 sm:px-6 lg:px-8 pt-7 pb-16">
        {view.name === 'dashboard' && <Campaigns user={user} onOpen={(id) => go('editor', { campaignId: id })} novaCampanhaSignal={novaCampanha} onNovaConsumed={() => setNovaCampanha(false)} />}
        {view.name === 'editor' && <Editor user={user} campaignId={view.campaignId} onBack={() => go('dashboard')} />}
        {view.name === 'catalogo' && isAdm && <Catalogo user={user} />}
        {view.name === 'parametros' && isAdm && <Parametros user={user} />}
        {view.name === 'equipe' && isAdm && <Equipe user={user} />}
      </main>

      <Notifications user={user} />
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  )
}
