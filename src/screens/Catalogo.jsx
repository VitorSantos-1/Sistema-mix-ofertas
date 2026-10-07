import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { money } from '../lib/format'
import { Upload, Search, FileSpreadsheet, CheckCircle2 } from 'lucide-react'

// normaliza cabeçalho: minúsculo, sem acento, sem espaços
const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, '')

function pick(row, keys) {
  const map = {}
  for (const k of Object.keys(row)) map[norm(k)] = row[k]
  for (const want of keys) { const v = map[want]; if (v !== undefined && v !== '') return v }
  return ''
}

function mapRows(rows) {
  return rows.map((r) => ({
    codigo: String(pick(r, ['codigo', 'codigointerno', 'codinterno', 'codint', 'cod', 'ean', 'plu', 'sku']) || '').trim(),
    descricao: String(pick(r, ['descricao', 'produto', 'nome', 'desc']) || '').trim(),
    mercadologico: String(pick(r, ['mercadologico', 'setor', 'categoria', 'grupo']) || 'Geral').trim(),
    preco_custo: toNum(pick(r, ['precocusto', 'custo', 'custounit'])),
    preco_venda: toNum(pick(r, ['precovenda', 'venda', 'preco', 'precodevenda'])),
    familia: String(pick(r, ['familia', 'codfamilia', 'cod_familia', 'fam', 'grupofamilia', 'familia_codigo']) || '').trim() || null,
  })).filter((p) => p.codigo && p.descricao)
}
function toNum(v) {
  if (v === '' || v === null || v === undefined) return null
  let s = String(v).trim().replace('R$', '').replace(/\s/g, '')
  if (s.includes(',') && s.includes('.')) {
    if (s.indexOf('.') < s.indexOf(',')) {
      s = s.replace(/\./g, '').replace(',', '.')
    } else {
      s = s.replace(/,/g, '')
    }
  } else if (s.includes(',')) {
    s = s.replace(',', '.')
  }
  const n = Number(s)
  return Number.isNaN(n) ? null : Math.round(n * 100) / 100
}

export default function Catalogo() {
  const toast = useToast()
  const fileRef = useRef(null)
  const [parsed, setParsed] = useState(null)   // {rows, name}
  const [importing, setImporting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [q, setQ] = useState('')
  const [prods, setProds] = useState([])
  const [searching, setSearching] = useState(false)

  async function search() {
    setSearching(true)
    try { const r = await api.searchProducts(q, 100); setProds(r.produtos || []) }
    catch (e) { toast(e.message, 'error') } finally { setSearching(false) }
  }
  useEffect(() => { search() }, []) // eslint-disable-line

  async function onFile(file) {
    if (!file) return
    try {
      const buf = await file.arrayBuffer()
      const wb = XLSX.read(buf, { type: 'array' })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const raw = XLSX.utils.sheet_to_json(ws, { defval: '' })
      const rows = mapRows(raw)
      if (!rows.length) { toast('Não encontrei colunas de código/descrição na planilha.', 'error'); return }
      setParsed({ rows, name: file.name })
    } catch {
      toast('Não foi possível ler o arquivo. Use CSV, XLS ou XLSX.', 'error')
    }
  }

  async function doImport() {
    if (!parsed?.rows?.length) return
    setImporting(true)
    try {
      const r = await api.importProducts(parsed.rows)
      toast(r.message || `${r.inseridos} produtos importados.`, 'success')
      setParsed(null); if (fileRef.current) fileRef.current.value = ''
      search()
    } catch (e) { toast(e.message, 'error') } finally { setImporting(false) }
  }

  return (
    <div>
      <h1 className="mb-4 font-display text-2xl font-bold">Catálogo de produtos</h1>

      {/* ---- IMPORTAÇÃO NO TOPO (item 7) ---- */}
      <div className="card overflow-hidden mb-5">
        <div className="flex items-center gap-2.5 px-4 sm:px-5 py-3 border-b border-line bg-surface-2/60">
          <div className="w-8 h-8 rounded-lg bg-brand/12 text-brand flex items-center justify-center shrink-0"><FileSpreadsheet size={17} /></div>
          <div className="leading-none">
            <h2 className="font-display text-sm font-semibold text-ink">Importar planilha de produtos</h2>
            <p className="text-[11px] text-ink-muted mt-1">Milhares de itens de uma vez — CSV, XLS ou XLSX</p>
          </div>
        </div>
        <div className="p-4 sm:p-5">
          <label htmlFor="import-file"
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); onFile(e.dataTransfer.files?.[0]) }}
            className={`group flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed py-9 px-4 text-center cursor-pointer transition-colors ${dragging ? 'border-brand bg-brand/[0.06]' : 'border-line hover:border-brand/50 hover:bg-brand/[0.03]'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${dragging ? 'bg-brand/15 text-brand' : 'bg-surface-2 text-ink-faint group-hover:bg-brand/10 group-hover:text-brand'}`}><Upload size={22} /></div>
            <div className="text-[13px] font-semibold text-ink">Clique para escolher um arquivo</div>
            <div className="text-[12px] text-ink-faint">ou arraste e solte aqui</div>
            <input id="import-file" ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={(e) => onFile(e.target.files?.[0])} className="hidden" />
          </label>

          {parsed && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 card-inset px-3 py-2.5 animate-fadeIn">
              <span className="chip bg-good/12 text-good"><CheckCircle2 size={14} /> {parsed.rows.length} itens válidos em “{parsed.name}”</span>
              <div className="flex items-center gap-2">
                <button className="btn btn-ghost" onClick={() => { setParsed(null); if (fileRef.current) fileRef.current.value = '' }}>Cancelar</button>
                <button className="btn btn-primary" onClick={doImport} disabled={importing}>
                  <Upload size={16} /> {importing ? 'Importando…' : `Importar ${parsed.rows.length}`}
                </button>
              </div>
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[12px]">
            <span className="font-medium text-ink-muted mr-0.5">Colunas aceitas:</span>
            {['código interno', 'descrição', 'mercadológico', 'família', 'custo', 'venda'].map((c) => (
              <span key={c} className="chip bg-surface-2 text-ink-muted !py-0.5">{c}</span>
            ))}
            <span className="text-ink-faint w-full mt-0.5">Nomes flexíveis · produtos existentes são atualizados.</span>
          </div>
        </div>
      </div>

      {/* ---- Busca ---- */}
      <div className="card overflow-hidden">
        <form className="flex gap-2 border-b border-line p-3" onSubmit={(e) => { e.preventDefault(); search() }}>
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input className="field pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por código, descrição ou setor…" />
          </div>
          <button className="btn btn-ghost" type="submit">Buscar</button>
        </form>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[12px] uppercase text-ink-faint">
                <th className="px-4 py-2">Código</th>
                <th className="px-4 py-2">Descrição</th>
                <th className="px-4 py-2">Mercadológico</th>
                <th className="px-4 py-2 text-center">Família</th>
                <th className="px-4 py-2 text-right">Custo</th>
                <th className="px-4 py-2 text-right">Venda</th>
              </tr>
            </thead>
            <tbody>
              {searching ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-faint">Buscando…</td></tr>
              ) : prods.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-faint">Nenhum produto.</td></tr>
              ) : prods.map((p) => (
                <tr key={p.codigo} className="border-b border-line/60">
                  <td className="px-4 py-2 font-mono text-[13px]">{p.codigo}</td>
                  <td className="px-4 py-2">{p.descricao}</td>
                  <td className="px-4 py-2 text-ink-muted">{p.mercadologico}</td>
                  <td className="px-4 py-2 text-center font-mono text-[12px]">
                    {p.familia ? <span className="chip bg-brand/10 text-brand font-semibold">{p.familia}</span> : <span className="text-ink-faint">—</span>}
                  </td>
                  <td className="px-4 py-2 text-right">{money(p.preco_custo)}</td>
                  <td className="px-4 py-2 text-right">{money(p.preco_venda)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
