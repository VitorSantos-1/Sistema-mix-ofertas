import { useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { Store, User, Lock, ArrowRight, ShieldCheck } from 'lucide-react'

const PERFIS = [
  { usuario: 'vitor', nome: 'Vitor', desc: 'Admin Data', shield: 'brand' },
  { usuario: 'allan', nome: 'Allan', desc: 'Gestor Comercial · Bebidas / Açougue', shield: 'app' },
  { usuario: 'edna', nome: 'Edna', desc: 'Merc Doce / Cereais' },
  { usuario: 'mario', nome: 'Mario', desc: 'Merc Salgada / Limpeza' },
  { usuario: 'jhonne', nome: 'Jhonne', desc: 'Frios / Peixaria' },
  { usuario: 'ana', nome: 'Ana', desc: 'Horti / Padaria' },
  { usuario: 'andreza', nome: 'Andreza', desc: 'Compradora' },
]

export default function Login({ onLogin }) {
  const toast = useToast()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!usuario.trim() || !senha) { toast('Informe usuário e senha.', 'error'); return }
    setLoading(true)
    try {
      const r = await api.login(usuario.trim(), senha)
      if (!r.success || !r.usuario) throw new Error('Usuário ou senha incorretos.')
      localStorage.setItem('auth_user', JSON.stringify(r.usuario))
      localStorage.setItem('auth_token', r.token || '')
      localStorage.setItem('op_name', r.usuario.nome || r.usuario.usuario || '')
      onLogin(r.usuario)
    } catch (err) {
      toast(err.message || 'Falha no login.', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-brand text-brand-ink flex items-center justify-center shadow-soft mb-3">
            <Store className="w-7 h-7" />
          </div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
            Supermercados <span className="text-brand">Opção</span>
          </h1>
          <p className="text-sm text-ink-muted mt-1 font-medium">Mix de Ofertas &amp; Encartes</p>
        </div>

        <div className="card p-6 sm:p-8 shadow-md">
          <form className="space-y-4" onSubmit={submit}>
            <div>
              <label className="label font-medium">Login do Comprador / ADM</label>
              <div className="relative mt-1.5">
                <User className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
                <input type="text" placeholder="ex.: allan, edna, mario..." className="field pl-10"
                  value={usuario} onChange={(e) => setUsuario(e.target.value)} autoFocus />
              </div>
            </div>
            <div>
              <label className="label font-medium">Senha Individual</label>
              <div className="relative mt-1.5">
                <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
                <input type="password" placeholder="Digite sua senha" className="field pl-10"
                  value={senha} onChange={(e) => setSenha(e.target.value)} />
              </div>
            </div>
            <button type="submit" disabled={loading} className="btn btn-primary w-full h-11 text-sm font-semibold tracking-wide shadow-sm mt-2">
              <span>{loading ? 'Entrando…' : 'Acessar Sistema'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-line">
            <div className="flex items-center justify-between mb-2.5">
              <span className="label font-medium">Selecione seu perfil</span>
              <span className="text-[11px] text-ink-faint">cada comprador vê seu setor</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {PERFIS.map((p) => (
                <button key={p.usuario} type="button" data-active={usuario === p.usuario}
                  onClick={() => setUsuario(p.usuario)}
                  className="group rounded-xl border border-line bg-surface p-2.5 text-left transition hover:border-brand/60 data-[active=true]:border-brand data-[active=true]:bg-brand/5">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-semibold text-ink group-data-[active=true]:text-brand">{p.nome}</span>
                    {p.shield && <ShieldCheck className={`w-3.5 h-3.5 opacity-80 ${p.shield === 'app' ? 'text-app' : 'text-brand'}`} />}
                  </div>
                  <div className="text-[11px] text-ink-faint mt-0.5 truncate">{p.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-[11px] text-ink-faint mt-5 text-center">Conectado ao banco de dados MySQL Central • Supermercados Opção</p>
      </div>
    </div>
  )
}
