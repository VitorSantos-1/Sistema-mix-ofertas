import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { Plus, Trash2, Pencil, X, Check, Package, SlidersHorizontal, Layers } from 'lucide-react'

// Rótulo amigável dos 3 tipos base; tipos criados pelo usuário mostram o próprio nome
const LABELS = { ENCARTE: 'Encarte', ALERTA: 'Alerta', FDS_SAZONAL: 'Fim de semana' }
const tipoLabel = (t) => LABELS[t] || t
// Converte para número respeitando o 0 (só cai no padrão se vier vazio/não-numérico).
const numOr = (x, def) => { const n = Number(x); return Number.isFinite(n) ? n : def }

export default function Parametros() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [users, setUsers] = useState([])
  const [tab, setTab] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // { kind:'novo'|'rename', ... }
  // Rascunho dos "Limites gerais": os campos editam este rascunho e só vão pro
  // banco quando o usuário clica em "Salvar" (nada é salvo sozinho ao sair do campo).
  const [poolDraft, setPoolDraft] = useState({})

  async function load(preferTab) {
    setLoading(true)
    try {
      const [p, u] = await Promise.all([api.getParametros(), api.listUsers()])
      setData(p)
      setUsers((u.usuarios || []).map((x) => x.usuario))
      const tipos = p._tipos || Object.keys(p).filter((k) => k !== '_tipos')
      setTab((cur) => preferTab || (cur && tipos.includes(cur) ? cur : tipos[0]))
    } catch (e) { toast(e.message, 'error') } finally { setLoading(false) }
  }
  useEffect(() => { load() }, []) // eslint-disable-line

  // Sincroniza o rascunho dos limites com o tipo atual (ao trocar de aba ou recarregar).
  useEffect(() => {
    if (!data || !tab) return
    setPoolDraft({ ...((data[tab] && data[tab].pool) || {}) })
  }, [tab, data])

  const tipos = useMemo(() => (data?._tipos || (data ? Object.keys(data).filter((k) => k !== '_tipos') : [])), [data])

  if (loading || !data) return <div className="py-20 text-center text-ink-faint">Carregando…</div>

  const bloco = (tab && data[tab]) || { params: [], pool: {} }
  const pool = bloco.pool || {}
  const usaPool = pool.pool_interna != null          // modo SALVO (tabela de mercadológicos)
  const usaPoolDraft = poolDraft.pool_interna != null // modo em edição (card de limites)

  // ── edição de mercadológicos ──
  const patchLocal = (id, patch) =>
    setData((d) => ({ ...d, [tab]: { ...d[tab], params: d[tab].params.map((r) => (r.id === id ? { ...r, ...patch } : r)) } }))

  async function saveRow(row, extra = {}) {
    try {
      await api.updateParametro(row.id, {
        comprador: row.comprador || null,
        meta_divulgacao: Number(row.meta_divulgacao) || 0,
        meta_interna: usaPool ? null : Number(row.meta_interna) || 0,
        ...extra,
      })
    } catch (e) { toast('Erro ao salvar. ' + e.message, 'error') }
  }

  async function renameMerc(row, novo) {
    const nome = (novo || '').trim().toUpperCase()
    if (!nome || nome === (row.mercadologico || '').toUpperCase()) return
    patchLocal(row.id, { mercadologico: nome })
    try { await api.updateParametro(row.id, { mercadologico: nome }) }
    catch (e) { toast('Erro ao renomear. ' + e.message, 'error') }
  }

  async function addMerc() {
    const nome = window.prompt('Nome do mercadológico:')
    if (!nome || !nome.trim()) return
    try {
      await api.createParametro({ tipo: tab, mercadologico: nome.trim().toUpperCase(), meta_divulgacao: 0, meta_interna: usaPool ? null : 0 })
      toast('Mercadológico adicionado.', 'success'); load(tab)
    } catch (e) { toast('Erro ao adicionar. ' + e.message, 'error') }
  }

  async function delMerc(row) {
    if (!confirm(`Remover "${row.mercadologico}" dos parâmetros de ${tipoLabel(tab)}?`)) return
    try { await api.deleteParametro(row.id); toast('Removido.', 'success'); load(tab) }
    catch (e) { toast(e.message, 'error') }
  }

  // ── limites / pool (rascunho + botão Salvar) ──
  const setDraft = (patch) => setPoolDraft((d) => ({ ...d, ...patch }))
  const toggleUsaPool = (on) => setDraft({ pool_interna: on ? numOr(poolDraft.pool_interna, 50) : null })
  // Há alterações não salvas nos limites?
  const poolDirty = ['capa_max', 'app_max', 'extra_pool'].some(
    (k) => numOr(pool[k], null) !== numOr(poolDraft[k], null)
  ) || ((pool.pool_interna == null) !== (poolDraft.pool_interna == null))
    || (poolDraft.pool_interna != null && numOr(pool.pool_interna, null) !== numOr(poolDraft.pool_interna, null))

  async function salvarLimites() {
    const usa = poolDraft.pool_interna != null
    try {
      await api.updatePool(tab, {
        pool_interna: usa ? numOr(poolDraft.pool_interna, 0) : null,
        extra_pool: numOr(poolDraft.extra_pool, 0),
        capa_max: numOr(poolDraft.capa_max, 16),
        app_max: numOr(poolDraft.app_max, 5),
      })
      toast('Limites salvos.', 'success')
      load(tab)
    } catch (e) { toast(e.message, 'error') }
  }

  // ── tipos ──
  async function criarTipo(form) {
    try {
      const r = await api.createTipo({
        nome: form.nome.trim(),
        usa_pool: form.usaPool,
        pool_interna: form.usaPool ? numOr(form.pool_interna, 50) : null,
        extra_pool: 0,
        capa_max: numOr(form.capa_max, 16),
        app_max: numOr(form.app_max, 5),
      })
      toast('Tipo criado.', 'success'); setModal(null); load(r.tipo)
    } catch (e) { toast(e.message, 'error') }
  }
  async function renomearTipo(novo) {
    try {
      const r = await api.renameTipo(tab, novo.trim())
      toast('Tipo renomeado.', 'success'); setModal(null); load(r.tipo)
    } catch (e) { toast(e.message, 'error') }
  }
  async function excluirTipo() {
    if (!confirm(`Excluir o tipo "${tipoLabel(tab)}" e todos os seus parâmetros?\n(Não é permitido se houver campanhas usando este tipo.)`)) return
    try { await api.deleteTipo(tab); toast('Tipo excluído.', 'success'); load() }
    catch (e) { toast(e.message, 'error') }
  }

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">Parâmetros e metas</h1>
          <p className="text-[12px] text-ink-faint mt-1">Crie tipos de campanha e defina os mercadológicos, compradores e metas de cada um.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ kind: 'novo', nome: '', usaPool: false, pool_interna: 50, capa_max: 16, app_max: 5 })}>
          <Plus className="w-4 h-4" /> Novo tipo
        </button>
      </div>

      {/* Abas de tipos (dinâmicas) */}
      <div className="seg overflow-x-auto scrollbar-none max-w-full">
        {tipos.map((t) => (
          <button key={t} data-active={tab === t} className="seg-item whitespace-nowrap" onClick={() => setTab(t)}>{tipoLabel(t)}</button>
        ))}
      </div>

      {/* Cabeçalho do tipo + ações */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-brand/12 text-brand flex items-center justify-center shrink-0"><Layers className="w-5 h-5" /></div>
          <div className="min-w-0">
            <h2 className="font-display text-lg font-bold text-ink truncate">{tipoLabel(tab)}</h2>
            <p className="text-[12px] text-ink-faint">{bloco.params.length} mercadológico(s) · limites próprios</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-ghost" onClick={() => setModal({ kind: 'rename', novo: tipoLabel(tab) })}><Pencil className="w-4 h-4" /> Renomear</button>
          <button className="btn btn-ghost !text-bad hover:!bg-bad/10" onClick={excluirTipo}><Trash2 className="w-4 h-4" /> Excluir tipo</button>
        </div>
      </div>

      {/* Limites gerais */}
      <div className="card p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-ink-faint" />
            <h3 className="text-[13px] font-semibold text-ink">Limites gerais</h3>
          </div>
          <div className="flex items-center gap-2">
            {poolDirty && <span className="chip bg-amber-500/15 text-amber-600 dark:text-amber-400">alterações não salvas</span>}
            <button className="btn btn-primary h-8" onClick={salvarLimites} disabled={!poolDirty}>
              <Check className="w-4 h-4" /> Salvar
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <PoolField label="Máx. Capa" value={poolDraft.capa_max} onChange={(v) => setDraft({ capa_max: v })} />
          <PoolField label="Máx. App Clube" value={poolDraft.app_max} onChange={(v) => setDraft({ app_max: v })} />
          {usaPoolDraft && <PoolField label="Pool interna (total)" value={poolDraft.pool_interna} onChange={(v) => setDraft({ pool_interna: v })} />}
          {usaPoolDraft && <PoolField label="Extra pool" value={poolDraft.extra_pool} onChange={(v) => setDraft({ extra_pool: v })} />}
        </div>

        {/* Modo da parte interna */}
        <div className="mt-4 pt-4 border-t border-line">
          <label className="label">Parte interna deste tipo</label>
          <div className="seg mt-1.5 inline-flex">
            <button type="button" data-active={!usaPoolDraft} className="seg-item" onClick={() => toggleUsaPool(false)}>Meta por mercadológico</button>
            <button type="button" data-active={usaPoolDraft} className="seg-item" onClick={() => toggleUsaPool(true)}>Pool compartilhado</button>
          </div>
          <p className="mt-2 text-[12px] text-ink-faint">
            {usaPoolDraft
              ? 'A parte interna usa um pool único compartilhado por todos os mercadológicos (a meta interna por linha fica desativada).'
              : 'Cada mercadológico tem a própria meta de itens internos.'}
            {poolDirty && ' — clique em Salvar para aplicar.'}
          </p>
        </div>
      </div>

      {/* Grid de mercadológicos */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-ink-faint" />
            <h3 className="text-[13px] font-semibold text-ink">Mercadológicos ({bloco.params.length})</h3>
          </div>
          <button className="btn btn-primary h-8" onClick={addMerc}><Plus className="w-4 h-4" /> Adicionar</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-faint bg-surface-2">
                <th className="px-4 py-2 min-w-[220px]">Mercadológico</th>
                <th className="px-4 py-2 w-44">Comprador</th>
                <th className="px-4 py-2 w-36">Meta divulgação</th>
                <th className="px-4 py-2 w-36">Meta interna</th>
                <th className="px-4 py-2 w-12"></th>
              </tr>
            </thead>
            <tbody>
              {bloco.params.map((row) => (
                <tr key={row.id} className="border-b border-line/60 hover:bg-surface-2/40">
                  <td className="px-3 py-1.5">
                    <input className="field h-9 font-semibold" defaultValue={row.mercadologico}
                      onBlur={(e) => renameMerc(row, e.target.value)} />
                  </td>
                  <td className="px-3 py-1.5">
                    <select className="field h-9" value={row.comprador || ''}
                      onChange={(e) => { patchLocal(row.id, { comprador: e.target.value }); saveRow({ ...row, comprador: e.target.value }) }}>
                      <option value="">— sem comprador —</option>
                      {users.map((u) => <option key={u} value={u}>{u}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <input type="number" min="0" className="field h-9 tnum" value={row.meta_divulgacao ?? 0}
                      onChange={(e) => patchLocal(row.id, { meta_divulgacao: e.target.value })}
                      onBlur={() => saveRow(row)} />
                  </td>
                  <td className="px-3 py-1.5">
                    {usaPool ? <span className="chip bg-surface-2 text-ink-faint">pool</span> : (
                      <input type="number" min="0" className="field h-9 tnum" value={row.meta_interna ?? 0}
                        onChange={(e) => patchLocal(row.id, { meta_interna: e.target.value })}
                        onBlur={() => saveRow(row)} />
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <button className="icon-btn h-8 w-8 !text-ink-faint hover:!text-bad" onClick={() => delMerc(row)} title="Remover"><Trash2 className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
              {bloco.params.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-ink-faint">Nenhum mercadológico ainda. Clique em “Adicionar”.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {modal?.kind === 'novo' && <NovoTipoModal modal={modal} setModal={setModal} onCreate={criarTipo} />}
      {modal?.kind === 'rename' && <RenameModal modal={modal} setModal={setModal} onSave={renomearTipo} />}
    </div>
  )
}

function PoolField({ label, value, onChange }) {
  // Controlado pelo rascunho do pai: digitar só altera o rascunho; salvar é no botão.
  return (
    <div>
      <label className="label">{label}</label>
      <input type="number" min="0" className="field h-9 mt-1.5 tnum" value={value ?? 0}
        onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function NovoTipoModal({ modal, setModal, onCreate }) {
  const [f, setF] = useState(modal)
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }))
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4 no-print animate-fadeIn" onClick={() => setModal(null)}>
      <form className="card w-full max-w-md shadow-lift overflow-hidden" onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); if (!f.nome.trim()) return; onCreate(f) }}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface-2/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand/12 text-brand flex items-center justify-center"><Plus className="w-4 h-4" /></div>
            <h2 className="font-display text-lg font-bold">Novo tipo de campanha</h2>
          </div>
          <button type="button" className="icon-btn" onClick={() => setModal(null)}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="label">Nome do tipo</label>
            <input className="field mt-1.5" autoFocus value={f.nome} onChange={(e) => set('nome', e.target.value)} placeholder="Ex.: Black Friday, Aniversário…" maxLength={60} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Máx. Capa</label><input type="number" min="0" className="field mt-1.5 tnum" value={f.capa_max} onChange={(e) => set('capa_max', e.target.value)} /></div>
            <div><label className="label">Máx. App Clube</label><input type="number" min="0" className="field mt-1.5 tnum" value={f.app_max} onChange={(e) => set('app_max', e.target.value)} /></div>
          </div>
          <div>
            <label className="label">Parte interna</label>
            <div className="seg mt-1.5">
              <button type="button" data-active={!f.usaPool} className="seg-item" onClick={() => set('usaPool', false)}>Meta por mercadológico</button>
              <button type="button" data-active={f.usaPool} className="seg-item" onClick={() => set('usaPool', true)}>Pool compartilhado</button>
            </div>
          </div>
          {f.usaPool && (
            <div><label className="label">Pool interna (total)</label><input type="number" min="0" className="field mt-1.5 tnum" value={f.pool_interna} onChange={(e) => set('pool_interna', e.target.value)} /></div>
          )}
          <p className="text-[12px] text-ink-faint">Depois de criar, adicione os mercadológicos, compradores e metas na tabela.</p>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-line bg-surface-2/40">
          <button type="button" className="btn btn-ghost" onClick={() => setModal(null)}>Cancelar</button>
          <button type="submit" className="btn btn-primary"><Plus className="w-4 h-4" /> Criar tipo</button>
        </div>
      </form>
    </div>
  )
}

function RenameModal({ modal, setModal, onSave }) {
  const [nome, setNome] = useState(modal.novo || '')
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4 no-print animate-fadeIn" onClick={() => setModal(null)}>
      <form className="card w-full max-w-md shadow-lift overflow-hidden" onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); if (!nome.trim()) return; onSave(nome) }}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface-2/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand/12 text-brand flex items-center justify-center"><Pencil className="w-4 h-4" /></div>
            <h2 className="font-display text-lg font-bold">Renomear tipo</h2>
          </div>
          <button type="button" className="icon-btn" onClick={() => setModal(null)}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-3">
          <label className="label">Novo nome</label>
          <input className="field mt-1.5" autoFocus value={nome} onChange={(e) => setNome(e.target.value)} maxLength={60} />
          <p className="text-[12px] text-ink-faint">As campanhas que já usam este tipo serão atualizadas automaticamente.</p>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-line bg-surface-2/40">
          <button type="button" className="btn btn-ghost" onClick={() => setModal(null)}>Cancelar</button>
          <button type="submit" className="btn btn-primary"><Check className="w-4 h-4" /> Salvar</button>
        </div>
      </form>
    </div>
  )
}
