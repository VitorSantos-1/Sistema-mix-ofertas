import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { Plus, KeyRound, UserCheck, UserX, X } from 'lucide-react'

const ROLES = [
  { id: 'comprador', label: 'Comprador' },
  { id: 'gestor', label: 'Gestor comercial' },
  { id: 'adm', label: 'Administrador' },
]

export default function Equipe() {
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ usuario: '', nome: '', senha: '', cargo: 'Comprador', role: 'comprador' })

  async function load() {
    setLoading(true)
    try { const r = await api.listUsers(); setUsers(r.usuarios || []) }
    catch (e) { toast(e.message, 'error') } finally { setLoading(false) }
  }
  useEffect(() => { load() }, []) // eslint-disable-line

  async function create(e) {
    e.preventDefault()
    if (!form.usuario.trim() || !form.nome.trim() || !form.senha) { toast('Preencha usuário, nome e senha.', 'error'); return }
    try {
      await api.createUser({ ...form, usuario: form.usuario.trim().toLowerCase(), nome: form.nome.trim() })
      toast('Usuário criado.', 'success')
      setCreating(false); setForm({ usuario: '', nome: '', senha: '', cargo: 'Comprador', role: 'comprador' })
      load()
    } catch (e) { toast(e.message, 'error') }
  }

  async function changeRole(u, role) {
    try { await api.updateUser(u.usuario, { role }); toast('Papel atualizado.', 'success'); load() }
    catch (e) { toast(e.message, 'error') }
  }
  async function toggleAtivo(u) {
    try { await api.updateUser(u.usuario, { ativo: u.ativo ? 0 : 1 }); load() }
    catch (e) { toast(e.message, 'error') }
  }
  async function resetPass(u) {
    const senha = window.prompt(`Nova senha para ${u.nome} (${u.usuario}):`)
    if (!senha) return
    try { await api.setPassword(u.usuario, senha); toast('Senha alterada.', 'success') }
    catch (e) { toast(e.message, 'error') }
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="font-display text-2xl font-bold">Equipe</h1>
        <span className="text-sm text-ink-faint">{users.length} usuários</span>
        <button className="btn btn-primary ml-auto" onClick={() => setCreating(true)}><Plus size={16} /> Novo usuário</button>
      </div>

      {loading ? <div className="py-20 text-center text-ink-faint">Carregando…</div> : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[12px] uppercase text-ink-faint">
                  <th className="px-4 py-2">Nome</th>
                  <th className="px-4 py-2">Usuário</th>
                  <th className="px-4 py-2">Cargo</th>
                  <th className="px-4 py-2 w-56">Papel</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Ações</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id || u.usuario} className="border-b border-line/60">
                    <td className="px-4 py-2 font-semibold">{u.nome}</td>
                    <td className="px-4 py-2 font-mono text-[13px]">{u.usuario}</td>
                    <td className="px-4 py-2 text-ink-muted">{u.cargo}</td>
                    <td className="px-4 py-2">
                      <select className="field py-1" value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                        {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-2">
                      {u.ativo ? <span className="chip bg-good/10 text-good">ativo</span> : <span className="chip bg-bad/10 text-bad">inativo</span>}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <button className="btn btn-ghost h-8" onClick={() => resetPass(u)} title="Redefinir senha"><KeyRound size={14} /> Senha</button>
                        {u.ativo ? (
                          <button className="btn btn-ghost h-8 !text-bad !border-bad/30 hover:!bg-bad/10" onClick={() => toggleAtivo(u)} title="Desativar acesso"><UserX size={14} /> Desativar</button>
                        ) : (
                          <button className="btn btn-primary h-8" onClick={() => toggleAtivo(u)} title="Reativar acesso"><UserCheck size={14} /> Ativar</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {creating && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 no-print" onClick={() => setCreating(false)}>
          <form className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-bold">Novo usuário</h2>
              <button type="button" onClick={() => setCreating(false)} className="text-ink-faint hover:text-ink"><X size={18} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2"><label className="mb-1 block text-sm font-semibold">Nome completo</label>
                <input className="field" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
              <div><label className="mb-1 block text-sm font-semibold">Usuário (login)</label>
                <input className="field" value={form.usuario} onChange={(e) => setForm({ ...form, usuario: e.target.value })} /></div>
              <div><label className="mb-1 block text-sm font-semibold">Senha</label>
                <input className="field" type="text" value={form.senha} onChange={(e) => setForm({ ...form, senha: e.target.value })} /></div>
              <div><label className="mb-1 block text-sm font-semibold">Cargo</label>
                <input className="field" value={form.cargo} onChange={(e) => setForm({ ...form, cargo: e.target.value })} /></div>
              <div><label className="mb-1 block text-sm font-semibold">Papel</label>
                <select className="field" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select></div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn btn-ghost" onClick={() => setCreating(false)}>Cancelar</button>
              <button type="submit" className="btn btn-primary"><Plus size={16} /> Criar</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
