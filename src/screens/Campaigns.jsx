import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import {
  Layers, TrendingUp, Star, Check, Search, Archive, Calendar,
  FileSpreadsheet, Copy, Trash2, ArrowRight, Plus, X, Pencil,
} from 'lucide-react'

const TABS = [
  { id: 'mes', label: 'Mês atual' },
  { id: 'Encarte', label: 'Encarte' },
  { id: 'Alerta', label: 'Alerta' },
  { id: 'FDS', label: 'Fim de semana' },
  { id: 'Virtual', label: 'Virtual' },
  { id: 'hist', label: 'Histórico' },
]
const emptyForm = { nome: '', tipo: '', periodo: '' }

// Rótulo amigável: nomes dos 3 tipos base; tipos criados pelo usuário mostram o próprio nome
const BASE_LABEL = { ENCARTE: 'Encarte', ALERTA: 'Alerta', FDS_SAZONAL: 'Fim de semana', FDS: 'Fim de semana' }
function tipoLabel(t) {
  const s = String(t || '').trim()
  return BASE_LABEL[s.toUpperCase()] || s
}
// Casa o tipo salvo de uma campanha com um tipo existente (exato, senão por palavra-chave)
function resolveTipo(tipo, tipos) {
  const s = String(tipo || '').trim()
  if (!s) return tipos[0] || 'ENCARTE'
  const exact = tipos.find((t) => t.toUpperCase() === s.toUpperCase())
  if (exact) return exact
  const u = s.toUpperCase()
  if (u.includes('FDS') || u.includes('SEMANA') || u.includes('SAZONAL')) return tipos.find((t) => t.toUpperCase().includes('FDS')) || s
  if (u.includes('ALERTA')) return tipos.find((t) => t.toUpperCase() === 'ALERTA') || s
  if (u.includes('ENCARTE')) return tipos.find((t) => t.toUpperCase() === 'ENCARTE') || s
  return s
}

export default function Campaigns({ user, onOpen, novaCampanhaSignal, onNovaConsumed }) {
  const toast = useToast()
  const isAdm = user.role === 'adm'
  const [camps, setCamps] = useState([])
  const [tab, setTab] = useState('mes')
  const [filtro, setFiltro] = useState('')
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState(null) // id da campanha em edição (null = criando)
  const [form, setForm] = useState(emptyForm)
  const [tipos, setTipos] = useState(['ENCARTE', 'ALERTA', 'FDS_SAZONAL']) // tipos definidos nos Parâmetros

  async function load() {
    try { const r = await api.listCampaigns(); setCamps(r.campanhas || []) }
    catch (e) { toast(e.message, 'error') }
  }
  async function loadTipos() {
    try { const p = await api.getParametros(); const ts = p._tipos || Object.keys(p).filter((k) => k !== '_tipos'); if (ts.length) setTipos(ts) }
    catch { /* mantém default */ }
  }
  useEffect(() => { load(); loadTipos() }, []) // eslint-disable-line
  // Consome o sinal: abre o modal SÓ quando o botão é clicado (não ao voltar pra aba)
  useEffect(() => {
    if (novaCampanhaSignal) { setEditId(null); setForm({ ...emptyForm, tipo: tipos[0] || 'ENCARTE' }); setCriando(true); onNovaConsumed?.() }
  }, [novaCampanhaSignal]) // eslint-disable-line

  function abrirEdicao(c) {
    setEditId(c.id)
    setForm({ nome: c.nome || '', tipo: resolveTipo(c.tipo, tipos), periodo: c.periodo || '' })
    setCriando(true)
  }

  const stats = useMemo(() => {
    const ativos = camps.filter((c) => c.status === 'ativa')
    const itens = camps.reduce((n, c) => n + (c.total_itens || 0), 0)
    const capa = camps.reduce((n, c) => n + (c.total_capa || 0), 0)
    const app = camps.reduce((n, c) => n + (c.total_app || 0), 0)
    const margens = camps.map((c) => c.margem_media).filter((m) => m > 0)
    const margem = margens.length ? (margens.reduce((a, b) => a + b, 0) / margens.length) : 0
    return { campanhas: ativos.length, itens, capa, app, margem }
  }, [camps])

  const lista = useMemo(() => {
    let l = camps
    if (tab === 'hist') l = l.filter((c) => c.status === 'arquivada')
    else if (tab === 'mes') l = l.filter((c) => c.status !== 'arquivada')
    else l = l.filter((c) => String(c.tipo || '').toUpperCase().includes(tab.toUpperCase()) && c.status !== 'arquivada')
    if (filtro.trim()) l = l.filter((c) => (c.nome || '').toLowerCase().includes(filtro.toLowerCase()))
    return l
  }, [camps, tab, filtro])

  async function criar(e) {
    e.preventDefault()
    if (!form.nome.trim()) { toast('Informe o nome da campanha.', 'error'); return }
    try {
      if (editId) {
        await api.updateCampaign(editId, { nome: form.nome.trim(), tipo: form.tipo, periodo: form.periodo })
        toast('Campanha atualizada.', 'success'); setCriando(false); setEditId(null); setForm(emptyForm); load()
      } else {
        const r = await api.createCampaign({ nome: form.nome.trim(), tipo: form.tipo, periodo: form.periodo, status: 'ativa' })
        toast('Campanha criada.', 'success'); setCriando(false); setForm(emptyForm)
        if (r.id) onOpen(r.id); else load()
      }
    } catch (e) { toast(e.message, 'error') }
  }
  function fecharModal() { setCriando(false); setEditId(null); setForm(emptyForm) }
  async function duplicar(id) { try { await api.duplicateCampaign(id); toast('Duplicada.', 'success'); load() } catch (e) { toast(e.message, 'error') } }
  async function excluir(c) { if (!confirm(`Excluir "${c.nome}"? Apaga todos os itens.`)) return; try { await api.deleteCampaign(c.id); toast('Excluída.', 'success'); load() } catch (e) { toast(e.message, 'error') } }
  async function arquivar() { if (!confirm('Arquivar as campanhas que já encerraram (período vencido)? As vigentes continuam no ar.')) return; try { const r = await api.archiveOld(); toast(r.message || 'Arquivadas.', 'success'); load() } catch (e) { toast(e.message, 'error') } }

  const statCards = [
    { label: 'Campanhas do mês', valor: stats.campanhas, Icon: Layers, sub: 'Ciclo mensal automático' },
    { label: 'Produtos no mix', valor: stats.itens, Icon: TrendingUp, sub: 'Itens em circulação' },
    { label: 'Destaques', valor: `${stats.capa} + ${stats.app}`, Icon: Star, sub: 'Capas + App Clube' },
    { label: 'Margem média', valor: `${stats.margem.toFixed(1)}%`, Icon: Check, sub: 'Rentabilidade global' },
  ]

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {statCards.map((s) => (
          <div key={s.label} className="card p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="label">{s.label}</p>
                <p className="font-display text-3xl font-bold text-ink mt-2 tnum">{s.valor}</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-brand/10 text-brand flex items-center justify-center"><s.Icon className="w-5 h-5" /></div>
            </div>
            <p className="text-[12px] text-ink-faint mt-3">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Filtro + abas */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="seg overflow-x-auto scrollbar-none max-w-full">
          {TABS.map((t) => (
            <button key={t.id} data-active={tab === t.id} className="seg-item whitespace-nowrap" onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input placeholder="Filtrar campanhas…" className="field pl-9 w-full sm:w-64" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          </div>
          {isAdm && (
            <button className="btn btn-ghost" title="Arquivar as campanhas já encerradas (período vencido)" onClick={arquivar}>
              <Archive className="w-4 h-4" /> <span className="hidden sm:inline">Virada de mês</span>
            </button>
          )}
        </div>
      </div>

      {/* Grid de campanhas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {lista.map((c) => (
          <div key={c.id} role="button" tabIndex={0} onClick={() => onOpen(c.id)}
            className="group card p-5 text-left flex flex-col justify-between cursor-pointer transition hover:shadow-lift hover:-translate-y-0.5 hover:border-brand/40">
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="chip bg-surface-2 text-ink-muted">{tipoLabel(c.tipo)}</span>
                {c.status === 'ativa'
                  ? <span className="chip bg-good/12 text-good"><span className="w-1.5 h-1.5 rounded-full bg-good"></span> No ar</span>
                  : <span className="chip bg-surface-2 text-ink-faint capitalize">{c.status}</span>}
              </div>
              <h4 className="font-display text-[15px] font-bold text-ink mt-3 group-hover:text-brand transition line-clamp-2">{c.nome}</h4>
              {c.periodo && (
                <div className="flex items-center gap-1.5 mt-2 text-xs text-ink-muted">
                  <Calendar className="w-3.5 h-3.5 text-ink-faint" /> {c.periodo}
                </div>
              )}
              <div className="grid grid-cols-3 gap-2 mt-4 card-inset p-3">
                <div className="text-center"><p className="label">Itens</p><p className="font-display text-base font-bold text-ink mt-1 tnum">{c.total_itens || 0}</p></div>
                <div className="text-center border-x border-line"><p className="label !text-brand">Capa</p><p className="font-display text-base font-bold text-brand mt-1 tnum">{c.total_capa || 0}/{c.capa_max ?? 16}</p></div>
                <div className="text-center"><p className="label !text-app">App</p><p className="font-display text-base font-bold text-app mt-1 tnum">{c.total_app || 0}/{c.app_max ?? 5}</p></div>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-line flex items-center justify-between">
              <div className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
                <a href={api.excelUrl(c.id)} className="icon-btn h-8 w-8" title="Exportar Excel"><FileSpreadsheet className="w-4 h-4" /></a>
                {isAdm && <button className="icon-btn h-8 w-8" title="Editar (nome, tipo, período)" onClick={() => abrirEdicao(c)}><Pencil className="w-4 h-4" /></button>}
                {isAdm && <button className="icon-btn h-8 w-8" title="Duplicar" onClick={() => duplicar(c.id)}><Copy className="w-4 h-4" /></button>}
                {isAdm && <button className="icon-btn h-8 w-8 hover:!text-bad" title="Excluir" onClick={() => excluir(c)}><Trash2 className="w-4 h-4" /></button>}
              </div>
              <span className="flex items-center gap-1 text-[13px] font-semibold text-brand group-hover:gap-2 transition-all">Abrir <ArrowRight className="w-4 h-4" /></span>
            </div>
          </div>
        ))}
        {lista.length === 0 && <div className="card p-10 text-center text-ink-faint md:col-span-2 lg:col-span-3">Nenhuma campanha aqui.</div>}
      </div>

      {/* Modal nova / editar campanha */}
      {criando && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4 no-print animate-fadeIn" onClick={fecharModal}>
          <form className="card w-full max-w-md shadow-lift overflow-hidden" onClick={(e) => e.stopPropagation()} onSubmit={criar}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface-2/60">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand/12 text-brand flex items-center justify-center">
                  {editId ? <Pencil className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                </div>
                <h2 className="font-display text-lg font-bold">{editId ? 'Editar campanha' : 'Nova campanha'}</h2>
              </div>
              <button type="button" className="icon-btn" onClick={fecharModal}><X className="w-4 h-4" /></button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="label">Nome</label>
                <input className="field mt-1.5" autoFocus value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Encarte Quinzenal Outubro" />
              </div>

              <div>
                <label className="label">Tipo</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1.5">
                  {tipos.map((t) => (
                    <button key={t} type="button" onClick={() => setForm({ ...form, tipo: t })}
                      className={`seg-item border justify-center ${form.tipo === t ? '!bg-brand !text-brand-ink border-brand' : 'border-line'}`}>
                      {tipoLabel(t)}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-ink-faint mt-1.5">Os tipos vêm de <b>Parâmetros</b> — crie novos lá com suas metas.</p>
              </div>

              <div>
                <label className="label flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> Período (vigência)</label>
                <input className="field mt-1.5" value={form.periodo} onChange={(e) => setForm({ ...form, periodo: e.target.value })} placeholder="Ex.: 06 a 26 de Outubro de 2026" />
                <p className="text-[11px] text-ink-faint mt-1.5">Livre — você pode alterar quando precisar (ex.: “06/10 a 26/10”).</p>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-6 py-4 border-t border-line bg-surface-2/40">
              <button type="button" className="btn btn-ghost" onClick={fecharModal}>Cancelar</button>
              <button type="submit" className="btn btn-primary">
                {editId ? <><Check className="w-4 h-4" /> Salvar</> : <><Plus className="w-4 h-4" /> Criar</>}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
