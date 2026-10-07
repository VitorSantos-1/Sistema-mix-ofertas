import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { getSocket } from '../lib/socket'
import { useToast } from '../lib/toast'
import { money, mixLabel, itemMargin, marginsByBuyer, avgMargin, pct, marginTone } from '../lib/format'
import {
  ArrowLeft, FileSpreadsheet, Printer, Plus, Trash2, Users, ShieldQuestion,
  Check, X, TrendingUp, Search, RotateCcw, Layers, Zap, Tag, Star, Smartphone, Clock,
  AlertTriangle, History, ArrowUpRight, ArrowDownRight, Minus,
} from 'lucide-react'

const DESTAQUES = ['', 'Capa', 'App', 'Dezão']

// Classes de chip por faixa de margem (usam os mesmos tokens do design original)
const TONE = {
  good: 'bg-good/10 text-good border border-good/30',
  warn: 'bg-warn/10 text-warn border border-warn/30',
  bad: 'bg-bad/10 text-bad border border-bad/30',
  faint: 'bg-surface-2 text-ink-faint border border-line',
}

// Conversão de número BR/US → float (2 casas). Corrige o bug de decimais.
function parseDecimal(val) {
  if (val === null || val === undefined || val === '') return null
  if (typeof val === 'number') return isNaN(val) ? null : val
  let s = String(val).trim().replace('R$', '').replace(/\s+/g, '')
  if (!s) return null
  if (s.includes(',') && s.includes('.')) {
    s = s.indexOf('.') < s.indexOf(',') ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, '')
  } else if (s.includes(',')) {
    s = s.replace(',', '.')
  }
  const n = parseFloat(s)
  return isNaN(n) ? null : Math.round(n * 100) / 100
}

// Exibe número para edição (ponto → vírgula), sem casas forçadas
function toInput(v) {
  if (v === null || v === undefined || v === '') return ''
  return String(v).replace('.', ',')
}

const emptyForm = {
  codigo: '', descricao: '', custo: '', mercadologico: '', parte: 'divulgacao',
  preco_oferta: '', preco_app: '', destaque: '', classificacao_mix: 2,
  familia: '', observacao: '', sellout: '',
}

export default function Editor({ user, campaignId, onBack }) {
  const toast = useToast()
  const [camp, setCamp] = useState(null)
  const [items, setItems] = useState([])
  const [ctx, setCtx] = useState(null)
  const [operators, setOperators] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [blocked, setBlocked] = useState(null)
  const [filtroComprador, setFiltroComprador] = useState('')
  const [permMap, setPermMap] = useState({})
  const [comparativo, setComparativo] = useState(null) // margens do período anterior
  const [compareId, setCompareId] = useState('')       // campanha escolhida p/ comparar ('' = automática)
  const codeRef = useRef(null)

  const role = ctx?.role || user.role
  const isAdm = role === 'adm'
  const isGestor = role === 'gestor'
  const isComprador = !isAdm && !isGestor
  const meusMerc = useMemo(() => (ctx?.meus_mercadologicos || []).map((m) => String(m).toUpperCase()), [ctx])

  const reloadCtx = useCallback(async () => {
    try { setCtx(await api.getContexto(campaignId, user.usuario)) } catch { /* ignore */ }
  }, [campaignId, user.usuario])

  // Comparativo de margens — compara com a campanha escolhida (ou a anterior automática)
  useEffect(() => {
    let alive = true
    api.getComparativo(campaignId, compareId).then((c) => { if (alive) setComparativo(c) })
    return () => { alive = false }
  }, [campaignId, compareId])

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const [detail, contexto] = await Promise.all([api.getCampaign(campaignId), api.getContexto(campaignId, user.usuario)])
        if (!alive) return
        setCamp(detail.campanha || detail)
        setItems(detail.itens || [])
        setCtx(contexto)
      } catch (e) { toast(e.message, 'error') }
    })()
    return () => { alive = false }
  }, [campaignId]) // eslint-disable-line

  // Tempo real
  useEffect(() => {
    const s = getSocket()
    const join = () => s.emit('join-campaign', { campaignId, usuario: user.usuario, nome: user.nome })
    join(); s.on('connect', join)

    const onAdded = ({ item }) => setItems((prev) => (prev.some((x) => x.id === item.id) ? prev.map((x) => x.id === item.id ? item : x) : [...prev, item]))
    const onUpdated = ({ itemId, field, value }) => setItems((prev) => prev.map((x) => (x.id === itemId ? { ...x, [field]: value } : x)))
    const onDeleted = ({ itemId }) => setItems((prev) => prev.filter((x) => x.id !== itemId))
    const onCotas = () => reloadCtx()
    const onBlockedMsg = ({ message, info, quota, mercadologico, parte }) => {
      toast(message, info ? 'success' : 'error')
      if (quota && mercadologico) setBlocked({ mercadologico, parte: parte || 'divulgacao' })
    }
    const onOps = (ops) => setOperators(Array.isArray(ops) ? ops : [])

    s.on('product-added-live', onAdded)
    s.on('item-field-updated-live', onUpdated)
    s.on('item-deleted-live', onDeleted)
    s.on('cotas-changed', onCotas)
    s.on('action-blocked', onBlockedMsg)
    s.on('operators-updated', onOps)
    s.on('operators-update', onOps)
    s.on('pedido-autorizacao', reloadCtx)
    s.on('autorizacao-resolvida', reloadCtx)

    return () => {
      s.off('connect', join); s.off('product-added-live', onAdded); s.off('item-field-updated-live', onUpdated)
      s.off('item-deleted-live', onDeleted); s.off('cotas-changed', onCotas); s.off('action-blocked', onBlockedMsg)
      s.off('operators-updated', onOps); s.off('operators-update', onOps)
      s.off('pedido-autorizacao', reloadCtx); s.off('autorizacao-resolvida', reloadCtx)
    }
  }, [campaignId, user.usuario, user.nome, reloadCtx])

  // Propriedade do item — recalcula ao vivo (corrige o bug de "não é meu / reiniciar")
  const canEdit = useCallback((it) => {
    if (isAdm || isGestor) return true
    const dono = (it.criado_por || '').trim().toLowerCase()
    if (dono) return dono === user.usuario.toLowerCase()
    return meusMerc.includes(String(it.mercadologico || '').toUpperCase())
  }, [isAdm, isGestor, meusMerc, user.usuario])

  function launch(e) {
    e?.preventDefault()
    if (!form.codigo.trim() || !form.descricao.trim()) { toast('Código e descrição são obrigatórios.', 'error'); return }
    if (!form.mercadologico || String(form.mercadologico).trim().toLowerCase() === 'geral') { toast('Selecione um setor mercadológico válido (não existe "Geral").', 'error'); return }
    const pOferta = parseDecimal(form.preco_oferta)
    if (pOferta == null || pOferta <= 0) { toast('Preço de oferta é obrigatório e maior que zero.', 'error'); return }

    getSocket().emit('fast-add-product', {
      campaignId, operatorName: user.nome,
      item: {
        codigo: form.codigo.trim(), descricao: form.descricao.trim(), mercadologico: form.mercadologico,
        parte: form.parte, preco_oferta: pOferta, custo: parseDecimal(form.custo), preco_app: parseDecimal(form.preco_app),
        destaque: form.destaque || null, classificacao_mix: Number(form.classificacao_mix) || 2,
        familia: form.familia ? String(form.familia).trim() : null, observacao: form.observacao || '',
        sellout: form.sellout || '', usuario: user.usuario,
      },
    })
    setForm((f) => ({ ...emptyForm, mercadologico: f.mercadologico, parte: f.parte }))
    codeRef.current?.focus()
  }

  function updateField(it, field, raw) {
    let value = raw
    if (['preco_oferta', 'preco_app', 'custo'].includes(field)) value = parseDecimal(raw)
    else if (field === 'classificacao_mix') value = Number(raw) || 2
    setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, [field]: value } : x)))
    getSocket().emit('update-item-field', { campaignId, itemId: it.id, field, value })
  }

  function removeItem(it) {
    if (!confirm(`Excluir "${it.descricao || it.codigo}"?`)) return
    getSocket().emit('delete-item', { campaignId, itemId: it.id })
  }

  function pedirAutorizacao(merc, parte) {
    getSocket().emit('pedir-autorizacao', { campaignId, mercadologico: merc, parte: parte || 'divulgacao', quantidade: 3 })
    setBlocked(null); toast('Pedido enviado ao ADM.', 'success')
  }
  function resolver(ped, aprovar, permanente = false) {
    getSocket().emit('resolver-autorizacao', { campaignId, pedidoId: ped.id, aprovar, quantidade: ped.quantidade || 3, permanente })
    setPermMap((m) => { const n = { ...m }; delete n[ped.id]; return n })
  }

  async function baixarExcel() {
    try {
      const params = {}
      if (isComprador) params.usuario = user.usuario
      else if (filtroComprador) params.comprador = filtroComprador
      const qs = new URLSearchParams(params).toString(); const qsStr = qs ? `?${qs}` : ''
      // App nativo (WebView2): salva na pasta Downloads pelo backend
      if (window.pywebview) {
        try {
          const r = await fetch(`/api/exportar/excel-salvar/${campaignId}${qsStr}`, { headers: { 'x-usuario': user.usuario } })
          const d = await r.json()
          if (d?.ok) { toast(`Planilha salva em Downloads: ${d.arquivo}`, 'success'); return }
        } catch { /* fallback download */ }
      }
      const res = await fetch(`/api/exportar/excel/${campaignId}${qsStr}`, { headers: { 'x-usuario': user.usuario } })
      if (!res.ok) throw new Error('Falha ao gerar a planilha.')
      const blob = await res.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url
      const disp = res.headers.get('content-disposition') || ''
      const m = disp.match(/filename="?([^";]+)"?/)
      a.download = m ? m[1] : `Mix_Ofertas_${camp?.nome || 'Campanha'}.xlsx`
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
      toast('Excel gerado.', 'success')
    } catch (e) { toast(`Erro ao exportar: ${e.message}`, 'error') }
  }

  // Todos os produtos válidos (base para métricas e margens)
  const produtos = useMemo(() => items.filter((i) => i.tipo_linha === 'produto' || i.codigo || i.descricao), [items])

  // Itens visíveis: comprador vê só os seus; adm/gestor veem tudo (com filtro opcional)
  const visibleItems = useMemo(() => {
    if (isComprador) return produtos.filter((i) => canEdit(i))
    if (filtroComprador) return produtos.filter((i) => (i.criado_por || '').trim().toLowerCase() === filtroComprador.toLowerCase())
    return produtos
  }, [produtos, isComprador, filtroComprador, canEdit])

  // Últimos lançamentos (feed) — os mais recentes primeiro
  const recentes = useMemo(() => [...visibleItems].slice(-8).reverse(), [visibleItems])

  const margemGeral = useMemo(() => avgMargin(produtos), [produtos])
  const margensPorComprador = useMemo(() => marginsByBuyer(produtos), [produtos])
  const minhaMargem = useMemo(() => {
    const meus = produtos.filter((i) => (i.criado_por || '').toLowerCase() === user.usuario.toLowerCase())
    return { margem: avgMargin(meus), qtd: meus.length }
  }, [produtos, user.usuario])

  // Métricas (6 cartões, como no original)
  const met = useMemo(() => {
    const base = isComprador ? visibleItems : produtos
    const divs = base.filter((i) => (i.parte || 'divulgacao').toLowerCase() !== 'interno').length
    const ints = base.filter((i) => (i.parte || '').toLowerCase() === 'interno').length
    const d = ctx?.cotas?.destaque || {}
    return {
      itens: base.length, divs, ints,
      capa: d.usado_capa ?? base.filter((i) => i.destaque === 'Capa').length, capaMax: d.capa_max ?? 16,
      app: d.usado_app ?? base.filter((i) => i.destaque === 'App').length, appMax: d.app_max ?? 5,
      margem: isComprador ? minhaMargem.margem : margemGeral,
    }
  }, [produtos, visibleItems, isComprador, ctx, margemGeral, minhaMargem])

  const mercOptions = (isAdm || isGestor) ? (ctx?.cotas?.linhas || []).map((l) => l.mercadologico) : (ctx?.meus_mercadologicos || [])

  if (!camp) return <div className="py-20 text-center text-ink-faint">Carregando campanha…</div>

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Cabeçalho da campanha */}
      <div className="card p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button className="icon-btn no-print" onClick={onBack} title="Voltar"><ArrowLeft className="w-[18px] h-[18px]" /></button>
          <div className="min-w-0">
            <h1 className="font-display text-lg font-bold text-ink leading-tight truncate">{camp.nome}</h1>
            <p className="text-[12px] text-ink-faint mt-0.5">{camp.tipo}{camp.periodo ? ` · ${camp.periodo}` : ''}</p>
          </div>
        </div>
        <div className="flex items-center flex-wrap gap-2 no-print">
          {operators.length > 0 && (
            <div className="hidden md:flex items-center gap-1.5 mr-1 text-ink-faint">
              <Users className="w-4 h-4" />
              {operators.map((o, i) => (
                <span key={i} className="chip" style={{ background: (o.color || '#888') + '22', color: o.color || '#555' }}>{o.nome || o.usuario}</span>
              ))}
            </div>
          )}
          <button className="btn btn-ghost" onClick={baixarExcel} title="Exportar planilha Excel">
            <FileSpreadsheet className="w-4 h-4" /> <span className="hidden sm:inline">Excel</span>
          </button>
          <button className="btn btn-ghost" onClick={() => window.print()} title="Imprimir / Gerar PDF">
            <Printer className="w-4 h-4" /> <span className="hidden sm:inline">Imprimir / PDF</span>
          </button>
        </div>
      </div>

      {/* Aviso de cota + pedir autorização (comprador) */}
      {blocked && isComprador && (
        <div className="card p-3 flex items-center gap-3 border-warn/40 bg-warn/10 no-print">
          <ShieldQuestion className="w-[18px] h-[18px] text-warn shrink-0" />
          <span className="text-sm text-ink">Cota de <b>{blocked.mercadologico}</b> ({blocked.parte}) esgotada.</span>
          <button className="btn btn-primary ml-auto" onClick={() => pedirAutorizacao(blocked.mercadologico, blocked.parte)}>Pedir autorização</button>
          <button className="icon-btn" onClick={() => setBlocked(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Pedidos de autorização (ADM) */}
      {isAdm && ctx?.pedidos?.length > 0 && (
        <div className="card p-4 no-print">
          <h3 className="label mb-2">Pedidos de autorização de cota</h3>
          <div className="flex flex-col gap-2">
            {ctx.pedidos.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center gap-2 card-inset px-3 py-2 text-sm">
                <span className="text-ink"><b>{p.comprador}</b> pede +{p.quantidade} em <b>{p.mercadologico}</b> ({p.parte})</span>
                <label className="flex items-center gap-1.5 text-[12px] text-ink-muted ml-auto cursor-pointer select-none"
                  title="Marcado: o extra vale para TODAS as campanhas deste tipo. Desmarcado: só nesta campanha.">
                  <input type="checkbox" checked={!!permMap[p.id]} onChange={(e) => setPermMap((m) => ({ ...m, [p.id]: e.target.checked }))} />
                  permanente
                </label>
                <button className="btn btn-primary" onClick={() => resolver(p, true, !!permMap[p.id])}><Check className="w-4 h-4" /> Aprovar</button>
                <button className="btn btn-ghost !text-bad" onClick={() => resolver(p, false)}><X className="w-4 h-4" /> Negar</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lançamento rápido */}
      <LaunchForm form={form} setForm={setForm} launch={launch} mercOptions={mercOptions} codeRef={codeRef} user={user} toast={toast} campaignId={campaignId} />

      {/* Últimos no mix (feed de lançamentos recentes) */}
      {recentes.length > 0 && (
        <div className="card p-3 sm:p-4 no-print">
          <div className="flex items-center gap-2 mb-2.5">
            <Clock className="w-4 h-4 text-ink-faint" />
            <h3 className="text-[13px] font-semibold text-ink">Últimos no mix</h3>
            <span className="text-[11px] text-ink-faint">últimos {recentes.length} lançamentos</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentes.map((it) => (
              <span key={it.id} className="chip bg-surface-2 text-ink-muted gap-1.5 max-w-full" title={it.descricao}>
                <span className="font-mono text-ink-faint shrink-0">{it.codigo}</span>
                <span className="truncate max-w-[200px]">{it.descricao}</span>
                <span className="font-mono font-semibold text-brand shrink-0">{money(it.preco_oferta)}</span>
                {(it.parte || 'divulgacao') === 'interno'
                  ? <span className="text-[10px] font-semibold text-ink-faint shrink-0">INT</span>
                  : <span className="text-[10px] font-semibold text-brand/70 shrink-0">DIV</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Cotas por mercadológico */}
      <CotasPanel cotas={ctx?.cotas} meusMerc={meusMerc} isAdm={isAdm} isGestor={isGestor} />

      {/* Métricas (6 cartões) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 no-print">
        <Metric label="Itens" value={met.itens} />
        <Metric label="Capa" value={`${met.capa}/${met.capaMax}`} accent="brand" />
        <Metric label="App Clube" value={`${met.app}/${met.appMax}`} accent="app" />
        <Metric label="Divulgação" value={met.divs} />
        <Metric label="Interno" value={met.ints} />
        <Metric label="Margem média" value={pct(met.margem)} />
      </div>

      {/* Margem média por comprador (com comparativo do período anterior) */}
      <div className="card p-3 sm:p-4 no-print">
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="flex items-center gap-1.5 text-[13px] font-semibold text-ink-muted">
            <TrendingUp className="w-4 h-4 text-brand" /> {(isAdm || isGestor) ? 'Margem por comprador' : 'Sua margem média'}
          </span>
          {(comparativo?.opcoes?.length) ? (
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <span className="text-[11px] text-ink-faint hidden md:inline">comparar com</span>
              <select className="field !h-8 !py-1 !px-2 text-[12px] w-auto max-w-[240px]" value={compareId}
                onChange={(e) => setCompareId(e.target.value)} title="Escolha a campanha/oferta para comparar as margens">
                <option value="">↺ Período anterior (automático)</option>
                {comparativo.opcoes.map((o) => (
                  <option key={o.id} value={o.id}>{o.nome}{o.periodo ? ` · ${o.periodo}` : ''}{o.mesmo_tipo ? '' : ' — outro tipo'}</option>
                ))}
              </select>
            </div>
          ) : <span className="text-[11px] text-ink-faint">sem outra campanha p/ comparar</span>}
        </div>
        {(isAdm || isGestor) ? (
          <div className="flex flex-wrap gap-2">
            <MargemCard label="Geral" tone={marginTone(margemGeral)} value={pct(margemGeral)} qtd={produtos.length}
              cur={margemGeral} prev={comparativo?.anterior?.margens?.geral}
              active={filtroComprador === ''} onClick={() => setFiltroComprador('')} />
            {margensPorComprador.map((m) => (
              <MargemCard key={m.dono} label={m.dono} capitalize tone={marginTone(m.margem)} value={pct(m.margem)} qtd={m.qtd}
                cur={m.margem} prev={comparativo?.anterior?.margens?.por?.[String(m.dono).toLowerCase()]?.margem}
                active={filtroComprador === m.dono} onClick={() => setFiltroComprador(filtroComprador === m.dono ? '' : m.dono)} />
            ))}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <MargemCard label="Você" tone={marginTone(minhaMargem.margem)} value={pct(minhaMargem.margem)} qtd={minhaMargem.qtd}
              cur={minhaMargem.margem} prev={comparativo?.anterior?.margens?.por?.[String(user.usuario).toLowerCase()]?.margem} />
          </div>
        )}
      </div>

      {/* Mix consolidado */}
      <Consolidado
        camp={camp} items={visibleItems} canEdit={canEdit} updateField={updateField} removeItem={removeItem}
        showComprador={isAdm || isGestor} filtroComprador={filtroComprador} setFiltroComprador={setFiltroComprador}
        compradoresLista={margensPorComprador.map((m) => m.dono)} user={user}
        showSellout={isAdm || String(user.usuario).toLowerCase() === 'andreza'}
      />
    </div>
  )
}

function Delta({ cur, prev }) {
  if (cur == null || prev == null) return null
  const d = cur - prev
  const t = Math.abs(d) < 0.05 ? 'flat' : d > 0 ? 'up' : 'down'
  const Icon = t === 'up' ? ArrowUpRight : t === 'down' ? ArrowDownRight : Minus
  const cls = t === 'up' ? 'text-good' : t === 'down' ? 'text-bad' : 'text-ink-faint'
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${cls}`} title="Variação vs período anterior">
      <Icon className="w-3 h-3" />{d > 0 ? '+' : ''}{d.toFixed(1)}pp
    </span>
  )
}

function MargemCard({ label, value, qtd, tone, cur, prev, active, onClick, capitalize }) {
  const border = tone === 'good' ? 'border-good/30' : tone === 'warn' ? 'border-warn/30' : tone === 'bad' ? 'border-bad/30' : 'border-line'
  const text = tone === 'good' ? 'text-good' : tone === 'warn' ? 'text-warn' : tone === 'bad' ? 'text-bad' : 'text-ink-faint'
  const bg = tone === 'good' ? 'bg-good/5' : tone === 'warn' ? 'bg-warn/5' : tone === 'bad' ? 'bg-bad/5' : 'bg-surface-2/60'
  const interactive = onClick ? 'cursor-pointer hover:shadow-soft hover:-translate-y-0.5 active:translate-y-0 active:scale-[.98]' : ''
  const ring = active ? 'ring-2 ring-brand ring-offset-1 ring-offset-surface' : ''
  const inner = (
    <>
      <div className={`text-[11px] font-semibold text-ink-muted truncate ${capitalize ? 'capitalize' : ''}`}>{label}</div>
      <div className="flex items-baseline gap-1.5 mt-0.5">
        <span className={`font-display text-lg font-bold tnum ${text}`}>{value}</span>
        <Delta cur={cur} prev={prev} />
      </div>
      <div className="text-[10px] text-ink-faint mt-0.5">{qtd} {qtd === 1 ? 'item' : 'itens'}</div>
    </>
  )
  if (!onClick) return <div className={`rounded-xl border ${border} ${bg} px-3 py-2 min-w-[130px]`}>{inner}</div>
  return (
    <button type="button" onClick={onClick} className={`text-left rounded-xl border ${border} ${bg} px-3 py-2 min-w-[130px] transition ${interactive} ${ring}`}>{inner}</button>
  )
}

function Metric({ label, value, accent }) {
  const color = accent === 'brand' ? 'text-brand' : accent === 'app' ? 'text-app' : 'text-ink'
  return (
    <div className="card px-4 py-3">
      <p className={`label ${accent === 'brand' ? '!text-brand' : accent === 'app' ? '!text-app' : ''}`}>{label}</p>
      <p className={`font-display text-2xl font-bold mt-1 tnum ${color}`}>{value}</p>
    </div>
  )
}

function MoneyInput({ value, onChange, className = '', placeholder }) {
  return (
    <div className="relative mt-1.5">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-ink-faint font-medium pointer-events-none">R$</span>
      <input inputMode="decimal" className={`field font-mono font-semibold pl-9 ${className}`} value={value} onChange={onChange} placeholder={placeholder} />
    </div>
  )
}

// Busca de produto por CÓDIGO ou NOME (igual ao original): digita e escolhe na lista;
// a descrição/custo/família vêm do catálogo (descrição não é editável).
function CodeSearch({ form, setForm, codeRef, toast }) {
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(-1)
  const tRef = useRef(null)
  const descRef = useRef(form.descricao)
  useEffect(() => { descRef.current = form.descricao }, [form.descricao])

  const applyProduct = useCallback((p) => {
    const temFamilia = !!p.familia
    setForm((f) => ({
      ...f,
      codigo: String(p.codigo || '').trim(),
      descricao: p.descricao || '',
      custo: p.preco_custo != null ? toInput(p.preco_custo) : f.custo,
      familia: p.familia || '',
      classificacao_mix: temFamilia ? 1 : f.classificacao_mix,
      // "Geral" não vale como setor — se o catálogo trouxer Geral/vazio, deixa em
      // branco pra forçar o usuário a escolher um mercadológico de verdade.
      mercadologico: f.mercadologico || ((String(p.mercadologico || '').trim().toLowerCase() === 'geral' ? '' : String(p.mercadologico || '').trim())),
    }))
    setOpen(false); setResults([]); setHi(-1)
    if (temFamilia) toast(`Família "${p.familia}" — Mix definido como "1 · Em família".`, 'success')
  }, [setForm, toast])

  const onChange = (e) => {
    const v = e.target.value
    // Ao mexer no código, limpa a descrição/família (só o catálogo preenche de volta)
    setForm((f) => ({ ...f, codigo: v, descricao: '', familia: '' }))
    if (tRef.current) clearTimeout(tRef.current)
    const q = v.trim()
    if (q.length < 2) { setResults([]); setOpen(false); return }
    tRef.current = setTimeout(async () => {
      try {
        const r = await api.searchProducts(q, 8)
        const list = r?.produtos || []
        setResults(list); setOpen(list.length > 0); setHi(list.length ? 0 : -1)
      } catch { setResults([]); setOpen(false) }
    }, 180)
  }

  const lookupExact = async () => {
    const cod = form.codigo.trim()
    if (!cod || descRef.current) return
    const p = await api.getProduct(cod)
    if (p) applyProduct(p)
    else if (/^\d+$/.test(cod)) toast(`Código ${cod} não encontrado no catálogo.`, 'error')
  }

  const onKeyDown = (e) => {
    if (open && results.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setHi((i) => (i + 1) % results.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHi((i) => (i - 1 + results.length) % results.length); return }
      if (e.key === 'Enter') { e.preventDefault(); applyProduct(results[hi >= 0 ? hi : 0]); return }
      if (e.key === 'Escape') { e.preventDefault(); setOpen(false); return }
    } else if (e.key === 'Enter') {
      // Sem lista aberta: procura o código exato antes de deixar o form gravar
      if (!descRef.current && form.codigo.trim()) { e.preventDefault(); lookupExact() }
    }
  }

  return (
    <div className="relative mt-1.5">
      <input
        ref={codeRef}
        className="field font-mono font-semibold"
        value={form.codigo}
        onChange={onChange}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => { setOpen(false); lookupExact() }, 140)}
        autoFocus
        placeholder="Código ou nome…"
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
      />
      {open && results.length > 0 && (
        <ul className="absolute z-30 mt-1 left-0 right-0 min-w-[300px] max-h-64 overflow-auto card p-1 shadow-lg">
          {results.map((p, i) => (
            <li key={`${p.codigo}-${i}`}>
              <button
                type="button"
                onMouseDown={(e) => { e.preventDefault(); applyProduct(p) }}
                onMouseEnter={() => setHi(i)}
                className={`w-full text-left px-2.5 py-1.5 rounded-md flex items-center gap-2 ${i === hi ? 'bg-brand/10' : 'hover:bg-surface-2'}`}
              >
                <span className="font-mono text-xs text-ink-muted shrink-0 w-16 truncate">{p.codigo}</span>
                <span className="text-sm text-ink truncate flex-1">{p.descricao}</span>
                {p.familia && <span className="chip bg-brand/10 text-brand shrink-0"><Layers className="w-3 h-3" /> {p.familia}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function LaunchForm({ form, setForm, launch, mercOptions, codeRef, user, toast, campaignId }) {
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setV = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  // Conflito de período + última oferta do produto (aparecem ao selecionar o código)
  const [conflito, setConflito] = useState(null)
  const [ultima, setUltima] = useState(null)
  useEffect(() => {
    const cod = (form.codigo || '').trim()
    if (!cod || !form.descricao) { setConflito(null); setUltima(null); return }
    let alive = true
    const t = setTimeout(async () => {
      try {
        const [cf, uo] = await Promise.all([
          api.checarConflito(cod, campaignId),
          api.ultimaOferta(cod, campaignId),
        ])
        if (!alive) return
        setConflito(cf && cf.conflito ? cf : null)
        setUltima(uo && uo.preco_oferta != null ? uo : null)
      } catch { if (alive) { setConflito(null); setUltima(null) } }
    }, 220)
    return () => { alive = false; clearTimeout(t) }
  }, [form.codigo, form.descricao, campaignId])
  const margem = useMemo(() => {
    const o = parseDecimal(form.preco_oferta), c = parseDecimal(form.custo)
    if (o && c != null && c > 0) return itemMargin({ custo: c, preco_oferta: o })
    return null
  }, [form.preco_oferta, form.custo])
  const lucro = useMemo(() => {
    const o = parseDecimal(form.preco_oferta), c = parseDecimal(form.custo)
    if (o != null && c != null) return o - c
    return null
  }, [form.preco_oferta, form.custo])
  const mTone = marginTone(margem)
  const mFill = mTone === 'good' ? 'bg-good' : mTone === 'warn' ? 'bg-warn' : mTone === 'bad' ? 'bg-bad' : 'bg-line'
  const mColor = margem == null ? 'text-ink-faint' : mTone === 'good' ? 'text-good' : mTone === 'warn' ? 'text-warn' : 'text-bad'
  const mW = margem == null ? 0 : Math.max(0, Math.min(100, margem))
  const destaques = [
    { v: 'Capa', label: 'Capa', active: '!bg-brand !text-brand-ink' },
    { v: 'App', label: 'App Clube', active: '!bg-app !text-app-ink' },
    { v: 'Dezão', label: '🔟 Dezão', active: '!bg-good !text-white' },
  ]

  return (
    <form className="card overflow-visible" onSubmit={launch}>
      {/* Cabeçalho */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-5 py-3 border-b border-line bg-surface-2/60">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-brand/12 text-brand flex items-center justify-center"><Zap className="w-4 h-4" /></div>
          <div className="leading-none">
            <h3 className="font-display text-sm font-semibold text-ink">Lançamento de ofertas</h3>
            <p className="text-[11px] text-ink-muted mt-1 flex items-center gap-1.5 flex-wrap">
              <span className="kbd">Código</span><span>→</span><span className="kbd">Oferta</span><span>→</span><span className="kbd">Mix</span><span>→</span><span className="text-good font-medium">grava</span>
            </p>
          </div>
        </div>
        <span className="chip bg-surface-2 text-ink-muted">{user?.nome || user?.usuario} · {(user?.role || '').toUpperCase()}</span>
      </div>

      <div className="p-4 sm:p-5 space-y-3">
        {/* Aviso de conflito de período (vermelho, em cima) — igual ao original */}
        {conflito && (
          <div className="flex items-start gap-2 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-[13px] font-medium text-bad animate-fadeIn">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span className="flex-1">{conflito.motivo || 'Este produto já está lançado em outra campanha com período sobreposto.'}</span>
          </div>
        )}
        {/* Informativo: preço da última oferta deste produto */}
        {ultima && (
          <div className="flex items-center gap-2 rounded-lg border border-app/30 bg-app/10 px-3 py-2 text-[13px] text-app animate-fadeIn">
            <History className="w-4 h-4 shrink-0" />
            <span className="flex-1">
              Última oferta: <b className="font-mono">{money(ultima.preco_oferta)}</b>
              {ultima.preco_app != null && <span className="opacity-80"> · App {money(ultima.preco_app)}</span>}
              {ultima.campanha_nome && <span className="opacity-70"> · {ultima.campanha_nome}{ultima.periodo ? ` (${ultima.periodo})` : ''}</span>}
            </span>
          </div>
        )}

        {/* Mercadológico + Parte */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[190px] flex-1 sm:flex-none">
            <label className="label font-medium">Mercadológico</label>
            <select className="field mt-1.5 font-semibold" value={form.mercadologico} onChange={set('mercadologico')}>
              <option value="">— selecione —</option>
              {mercOptions.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="label font-medium">Parte</label>
            <div className="seg mt-1.5">
              <button type="button" data-active={form.parte === 'divulgacao'} className="seg-item" onClick={() => setV('parte', 'divulgacao')}>Divulgação</button>
              <button type="button" data-active={form.parte === 'interno'} className="seg-item" onClick={() => setV('parte', 'interno')}>Interno</button>
            </div>
          </div>
          {form.familia && <span className="chip bg-brand/10 text-brand mb-1"><Layers className="w-3.5 h-3.5" /> Família: {form.familia}</span>}
        </div>

        {/* Campos (grid 12 col) */}
        <div className="grid grid-cols-2 md:grid-cols-12 gap-3">
          <div className="col-span-2 md:col-span-3">
            <label className="label">1 · Código *</label>
            <CodeSearch form={form} setForm={setForm} codeRef={codeRef} toast={toast} />
          </div>
          <div className="col-span-2 md:col-span-6">
            <label className="label">Descrição</label>
            <input className="field mt-1.5 !bg-surface-2/50 text-ink-muted cursor-default" value={form.descricao} readOnly tabIndex={-1} placeholder="Selecione o código…" title="Preenchida automaticamente pelo catálogo" />
          </div>
          <div className="col-span-2 md:col-span-3">
            <label className="label">Custo (R$)</label>
            <MoneyInput value={form.custo} onChange={set('custo')} placeholder="0,00" />
          </div>

          <div className="col-span-1 md:col-span-2">
            <label className="label text-brand font-semibold">2 · Oferta (R$) *</label>
            <MoneyInput value={form.preco_oferta} onChange={set('preco_oferta')} className="text-brand" placeholder="0,00" />
          </div>
          <div className="col-span-1 md:col-span-2">
            <label className="label text-app">3 · App (R$)</label>
            <MoneyInput value={form.preco_app} onChange={set('preco_app')} className="text-app" placeholder="opcional" />
          </div>
          <div className="col-span-1 md:col-span-2">
            <label className="label">4 · Mix *</label>
            <select className="field mt-1.5" value={form.classificacao_mix} onChange={set('classificacao_mix')}>
              <option value={2}>2 · Unitário</option>
              <option value={1}>1 · Em família</option>
            </select>
          </div>
          <div className="col-span-1 md:col-span-2">
            <label className="label">5 · Sellout</label>
            <input className="field mt-1.5" value={form.sellout} onChange={set('sellout')} placeholder="opcional" />
          </div>
          <div className="col-span-2 md:col-span-4">
            <label className="label">6 · Observação</label>
            <input className="field mt-1.5" value={form.observacao} onChange={set('observacao')} placeholder="opcional" />
          </div>

          {/* Margem + Lucro */}
          <div className="col-span-2 md:col-span-12">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-baseline justify-between mb-1">
                  <span className="label">Margem</span>
                  <span className={`font-mono text-sm font-semibold tnum ${mColor}`}>{pct(margem)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                  <div className={`h-full rounded-full transition-[width] duration-300 ${mFill}`} style={{ width: mW + '%' }} />
                </div>
              </div>
              <div className="text-right shrink-0 w-24">
                <div className="label">Lucro un.</div>
                <div className={`font-mono text-sm font-semibold tnum mt-1 ${lucro == null ? 'text-ink-faint' : lucro < 0 ? 'text-bad' : 'text-ink'}`}>{lucro == null ? '—' : money(lucro)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Destaque + Gravar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-line">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="label mr-0.5">Destaque</span>
            {destaques.map((d) => (
              <button key={d.v} type="button" data-active={form.destaque === d.v}
                className={`seg-item border border-line ${form.destaque === d.v ? d.active : ''}`}
                onClick={() => setV('destaque', form.destaque === d.v ? '' : d.v)}>
                {d.label}
              </button>
            ))}
          </div>
          <button type="submit" className="btn btn-primary font-semibold">
            Gravar produto <span className="kbd !bg-brand-ink/15 !text-brand-ink !border-brand-ink/25 ml-1">Enter</span>
          </button>
        </div>
      </div>
    </form>
  )
}

function CotaBar({ label, used, lim }) {
  const ratio = lim > 0 ? used / lim : 0
  const w = Math.min(100, Math.round(ratio * 100))
  const fill = ratio >= 1 ? 'bg-bad' : ratio >= 0.8 ? 'bg-warn' : 'bg-good'
  const txt = ratio >= 1 ? 'text-bad font-semibold' : 'text-ink-muted'
  return (
    <div className="mt-1.5 flex items-center gap-2">
      <span className="w-14 text-ink-faint shrink-0">{label}</span>
      <div className="flex-1">
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
          <div className={`h-full rounded-full transition-[width] duration-300 ${fill}`} style={{ width: w + '%' }} />
        </div>
      </div>
      <span className={`font-mono tnum w-12 text-right shrink-0 ${txt}`}>{used}/{lim}</span>
    </div>
  )
}

function CotasPanel({ cotas, meusMerc, isAdm, isGestor }) {
  if (!cotas) return null
  const linhas = (cotas.linhas || []).filter((l) => isAdm || isGestor || meusMerc.includes(String(l.mercadologico).toUpperCase()))
  if (linhas.length === 0) return null
  const poolLim = cotas.pool ? (cotas.pool.pool_interna + (cotas.pool.extra_pool || 0)) : 0
  return (
    <div className="card p-4 sm:p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-semibold text-ink">Cotas por mercadológico</h3>
        {cotas.pool && (
          <span className={`chip ${cotas.pool.usado >= poolLim ? 'bg-bad/12 text-bad' : 'bg-app/12 text-app'}`}>
            Pool interno {cotas.pool.usado}/{poolLim}
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3">
        {linhas.map((l) => {
          const divLim = l.meta_divulgacao + (l.extra_div || 0)
          const intLim = l.meta_interna != null ? l.meta_interna + (l.extra_int || 0) : null
          return (
            <div key={l.id} className="text-[12px]">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-ink truncate">{l.mercadologico}</span>
                {l.comprador && <span className="text-ink-faint truncate">{l.comprador}</span>}
              </div>
              <CotaBar label="Divulg." used={l.usado_divulgacao} lim={divLim} />
              {intLim != null && <CotaBar label="Interna" used={l.usado_interna} lim={intLim} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Consolidado({ camp, items, canEdit, updateField, removeItem, showComprador, filtroComprador, setFiltroComprador, compradoresLista, user, showSellout }) {
  const [busca, setBusca] = useState('')
  const [filtroMerc, setFiltroMerc] = useState('')
  const [filtroParte, setFiltroParte] = useState('')
  const [soSellout, setSoSellout] = useState(false)

  const mercs = useMemo(() => {
    const s = new Set()
    for (const it of items) if (it.mercadologico) s.add(it.mercadologico.trim().toUpperCase())
    return Array.from(s).sort()
  }, [items])

  const filtrados = useMemo(() => items.filter((it) => {
    if (busca) {
      const b = busca.toLowerCase()
      if (![it.codigo, it.descricao, it.familia].some((v) => String(v || '').toLowerCase().includes(b))) return false
    }
    if (filtroMerc && String(it.mercadologico || '').trim().toUpperCase() !== filtroMerc) return false
    if (filtroParte) {
      const p = (it.parte || 'divulgacao').toLowerCase()
      if (filtroParte === 'interno' ? p !== 'interno' : p === 'interno') return false
    }
    if (soSellout && String(it.sellout || '').trim() === '') return false
    return true
  }), [items, busca, filtroMerc, filtroParte, soSellout])

  const agrupar = (parteInterno) => {
    const g = {}
    for (const it of filtrados) {
      const ehInt = (it.parte || '').toLowerCase() === 'interno'
      if (ehInt !== parteInterno) continue
      const k = (it.mercadologico || 'GERAL').toUpperCase()
      ;(g[k] = g[k] || []).push(it)
    }
    return Object.entries(g).sort((a, b) => a[0].localeCompare(b[0]))
  }
  const gruposDiv = useMemo(() => agrupar(false), [filtrados])
  const gruposInt = useMemo(() => agrupar(true), [filtrados])
  const nDiv = gruposDiv.reduce((n, [, its]) => n + its.length, 0)
  const nInt = gruposInt.reduce((n, [, its]) => n + its.length, 0)
  const temFiltro = busca || filtroMerc || filtroParte || filtroComprador || soSellout

  return (
    <div className="card overflow-hidden print-sheet">
      {/* Cabeçalho de impressão */}
      <div className="hidden print:block text-center pb-2 mb-2 border-b border-line">
        <div className="font-display font-bold text-lg text-brand uppercase">Supermercados Opção</div>
        <div className="text-sm font-semibold">{camp.nome}{camp.periodo ? ` — ${camp.periodo}` : ''}</div>
        <div className="text-[11px] text-ink-muted mt-0.5">
          Mix consolidado · {showComprador ? (filtroComprador ? `Comprador: ${filtroComprador}` : 'Todos os compradores') : `Comprador: ${user?.nome || user?.usuario}`} · {filtrados.length} itens
        </div>
      </div>

      {/* Barra de filtros (não imprime) */}
      <div className="px-4 py-3 border-b border-line no-print">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="font-display text-[15px] font-bold text-ink">Mix consolidado</h2>
            <p className="text-[12px] text-ink-faint">{filtrados.length} {filtrados.length === 1 ? 'item' : 'itens'}{filtroComprador ? ` · ${filtroComprador}` : ''}</p>
          </div>
          {temFiltro && (
            <button className="btn btn-ghost !text-brand" onClick={() => { setBusca(''); setFiltroMerc(''); setFiltroParte(''); setFiltroComprador?.(''); setSoSellout(false) }}>
              <RotateCcw className="w-3.5 h-3.5" /> Limpar filtros
            </button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input className="field pl-9" placeholder="Buscar código, descrição ou família…" value={busca} onChange={(e) => setBusca(e.target.value)} />
          </div>
          <select className="field w-auto" value={filtroMerc} onChange={(e) => setFiltroMerc(e.target.value)}>
            <option value="">Todos os setores</option>
            {mercs.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="field w-auto" value={filtroParte} onChange={(e) => setFiltroParte(e.target.value)}>
            <option value="">Divulgação + Interno</option>
            <option value="divulgacao">Só Divulgação</option>
            <option value="interno">Só Interno</option>
          </select>
          {showComprador && (
            <select className="field w-auto" value={filtroComprador || ''} onChange={(e) => setFiltroComprador(e.target.value)}>
              <option value="">Todos os compradores</option>
              {compradoresLista.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          )}
          {showSellout && (
            <button type="button" onClick={() => setSoSellout((v) => !v)}
              className={`btn ${soSellout ? 'btn-primary' : 'btn-ghost'} whitespace-nowrap`}
              title="Mostrar somente itens que têm Sellout preenchido">
              <Tag className="w-3.5 h-3.5" /> Só com sellout
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[13px] print-table">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-ink-faint border-b border-line bg-surface-2">
              <th className="px-3 py-2 w-24">Código</th>
              <th className="px-3 py-2 min-w-[220px]">Descrição</th>
              <th className="px-3 py-2 w-24 text-right">Oferta</th>
              <th className="px-3 py-2 w-24 text-right">App</th>
              <th className="px-3 py-2 w-20 text-right">Margem</th>
              <th className="px-3 py-2 w-28">Mix</th>
              <th className="px-3 py-2 w-28">Parte</th>
              <th className="px-3 py-2 w-24">Sellout</th>
              <th className="px-3 py-2 min-w-[120px]">Obs</th>
              <th className="px-3 py-2 w-24">Destaque</th>
              {showComprador && <th className="px-3 py-2 w-24">Comprador</th>}
              <th className="px-3 py-2 w-10 no-print"></th>
            </tr>
          </thead>
          <tbody>
            <SectionBanner label={`📢 Ofertas de Divulgação (${nDiv})`} cls="print-banner-div bg-brand text-brand-ink" />
            {gruposDiv.map(([merc, its]) => (
              <GroupSection key={'d_' + merc} merc={merc} its={its} isDiv canEdit={canEdit} updateField={updateField} removeItem={removeItem} showComprador={showComprador} />
            ))}
            {nDiv === 0 && <EmptyRow>Nenhuma oferta de divulgação.</EmptyRow>}

            <SectionBanner label={`📦 Ofertas Internas (${nInt})`} cls="print-banner-int bg-ink text-white" />
            {gruposInt.map(([merc, its]) => (
              <GroupSection key={'i_' + merc} merc={merc} its={its} isDiv={false} canEdit={canEdit} updateField={updateField} removeItem={removeItem} showComprador={showComprador} />
            ))}
            {nInt === 0 && <EmptyRow>Nenhuma oferta interna.</EmptyRow>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SectionBanner({ label, cls }) {
  return (
    <tr className={`font-bold ${cls}`}>
      <td colSpan={99} className="px-3 py-2 text-xs uppercase tracking-wider">{label}</td>
    </tr>
  )
}
function EmptyRow({ children }) {
  return <tr><td colSpan={99} className="px-4 py-6 text-center text-xs text-ink-faint italic">{children}</td></tr>
}

function GroupSection({ merc, its, isDiv, canEdit, updateField, removeItem, showComprador }) {
  const m = avgMargin(its)
  return (
    <>
      <tr className={`border-y border-line font-semibold ${isDiv ? 'print-merc-div bg-brand/10 text-ink' : 'print-merc-int bg-surface-2 text-ink'}`}>
        <td colSpan={99} className="px-3 py-1.5 text-xs font-bold uppercase tracking-wide">
          ▶ {merc} <span className="opacity-70 font-normal">· {its.length} {its.length === 1 ? 'produto' : 'produtos'} · margem {pct(m)}</span>
        </td>
      </tr>
      {its.map((it) => (
        <ProductRow key={it.id} it={it} editable={canEdit(it)} updateField={updateField} removeItem={removeItem} showComprador={showComprador} />
      ))}
    </>
  )
}

const CELL = 'w-full bg-transparent px-2 py-1.5 rounded-md focus:outline-none focus:bg-surface focus:ring-1 focus:ring-brand/40 transition-colors'
const MTONE = { good: 'bg-good/12 text-good', warn: 'bg-warn/12 text-warn', bad: 'bg-bad/12 text-bad', faint: 'bg-surface-2 text-ink-faint' }

function DestBtn({ active, tone, title, onClick, children }) {
  const on = tone === 'brand' ? 'text-brand bg-brand/12 ring-1 ring-brand/30' : tone === 'app' ? 'text-app bg-app/12 ring-1 ring-app/30' : 'text-good bg-good/12 ring-1 ring-good/30'
  return (
    <button type="button" title={title} onClick={onClick}
      className={`p-1.5 rounded-md transition-all duration-150 hover:scale-110 active:scale-90 ${active ? on : 'text-ink-faint hover:text-ink hover:bg-surface-2'}`}>
      {children}
    </button>
  )
}

// Base dos "chips-botão" clicáveis do consolidado (Mix / Parte) — interativos e discretos
const CHIP_BTN = 'chip cursor-pointer text-[13px] select-none transition-all duration-150 hover:shadow-soft hover:ring-1 active:scale-95'

function ProductRow({ it, editable, updateField, removeItem, showComprador }) {
  const margem = itemMargin(it)
  const isFam = Number(it.classificacao_mix) === 1
  const isInterno = (it.parte || 'divulgacao') === 'interno'
  return (
    <tr className="border-b border-line/60 align-middle hover:bg-surface-2/40">
      <td className="px-2 py-1 font-mono text-ink-muted whitespace-nowrap">{it.codigo}</td>
      <td className="px-2 py-1 font-medium text-ink desc-full min-w-[200px]">{it.descricao}</td>

      {/* Oferta */}
      <td className="px-1 py-1 text-right">
        {editable ? (
          <>
            <input inputMode="decimal" defaultValue={toInput(it.preco_oferta)} onBlur={(e) => updateField(it, 'preco_oferta', e.target.value)}
              className={`${CELL} text-right font-mono font-semibold text-brand`} />
            <span className="hidden print:inline font-semibold tnum">{money(it.preco_oferta)}</span>
          </>
        ) : <span className="font-semibold tnum">{money(it.preco_oferta)}</span>}
      </td>
      {/* App */}
      <td className="px-1 py-1 text-right">
        {editable ? (
          <>
            <input inputMode="decimal" defaultValue={toInput(it.preco_app)} onBlur={(e) => updateField(it, 'preco_app', e.target.value)}
              className={`${CELL} text-right font-mono text-app`} placeholder="—" />
            <span className="hidden print:inline tnum">{money(it.preco_app)}</span>
          </>
        ) : <span className="tnum">{money(it.preco_app)}</span>}
      </td>
      {/* Margem — chip colorido */}
      <td className="px-2 py-1 text-center">
        <span className={`chip justify-center font-mono text-[13px] ${MTONE[marginTone(margem)]}`}>{pct(margem)}</span>
      </td>
      {/* Mix — chip clicável */}
      <td className="px-2 py-1 text-center whitespace-nowrap">
        {editable ? (
          <>
            <button type="button" onClick={() => updateField(it, 'classificacao_mix', isFam ? 2 : 1)}
              className={`${CHIP_BTN} ${isFam ? 'bg-app/12 text-app hover:ring-app/40' : 'bg-surface-2 text-ink-muted hover:ring-line'}`} title="Clique para alternar Mix">
              {mixLabel(it.classificacao_mix)}
            </button>
            <span className="hidden print:inline">{mixLabel(it.classificacao_mix)}</span>
          </>
        ) : <span>{mixLabel(it.classificacao_mix)}</span>}
      </td>
      {/* Parte — chip clicável (Divulgação / Interno) */}
      <td className="px-2 py-1 text-center whitespace-nowrap">
        {editable ? (
          <>
            <button type="button" onClick={() => updateField(it, 'parte', isInterno ? 'divulgacao' : 'interno')}
              className={`${CHIP_BTN} ${isInterno ? 'bg-ink/10 text-ink hover:ring-ink/30' : 'bg-brand/12 text-brand hover:ring-brand/40'}`} title="Clique para alternar Divulgação/Interno">
              {isInterno ? 'Interno' : 'Divulgação'}
            </button>
            <span className="hidden print:inline">{isInterno ? 'Interno' : 'Divulgação'}</span>
          </>
        ) : <span>{isInterno ? 'Interno' : 'Divulgação'}</span>}
      </td>
      {/* Sellout */}
      <td className="px-1 py-1">
        {editable ? (
          <>
            <input defaultValue={it.sellout || ''} onBlur={(e) => updateField(it, 'sellout', e.target.value)} className={CELL} placeholder="—" />
            <span className="hidden print:inline">{it.sellout || '—'}</span>
          </>
        ) : <span>{it.sellout || '—'}</span>}
      </td>
      {/* Observação */}
      <td className="px-1 py-1">
        {editable ? (
          <>
            <input defaultValue={it.observacao || ''} onBlur={(e) => updateField(it, 'observacao', e.target.value)} className={CELL} placeholder="—" />
            <span className="hidden print:inline">{it.observacao || '—'}</span>
          </>
        ) : <span>{it.observacao || '—'}</span>}
      </td>
      {/* Destaque — botões clicáveis */}
      <td className="px-2 py-1">
        {editable ? (
          <>
            <div className="flex items-center justify-center gap-0.5">
              <DestBtn active={it.destaque === 'Capa'} tone="brand" title="Capa" onClick={() => updateField(it, 'destaque', it.destaque === 'Capa' ? '' : 'Capa')}><Star className="w-4 h-4" /></DestBtn>
              <DestBtn active={it.destaque === 'App'} tone="app" title="App Clube" onClick={() => updateField(it, 'destaque', it.destaque === 'App' ? '' : 'App')}><Smartphone className="w-4 h-4" /></DestBtn>
              <DestBtn active={it.destaque === 'Dezão'} tone="good" title="Dezão" onClick={() => updateField(it, 'destaque', it.destaque === 'Dezão' ? '' : 'Dezão')}><span className="text-[12px] font-bold leading-none">🔟</span></DestBtn>
            </div>
            <span className="hidden print:inline">{it.destaque || '—'}</span>
          </>
        ) : <span>{it.destaque || '—'}</span>}
      </td>

      {showComprador && <td className="px-2 py-1 text-ink-muted whitespace-nowrap">{it.criado_por || '—'}</td>}

      <td className="px-2 py-1 no-print text-center">
        {editable && <button className="icon-btn h-8 w-8 !text-ink-faint hover:!text-bad" onClick={() => removeItem(it)} title="Excluir"><Trash2 className="w-4 h-4" /></button>}
      </td>
    </tr>
  )
}
