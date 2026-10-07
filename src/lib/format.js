export function money(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function mixLabel(m) {
  if (m === 1 || m === '1') return '1 · Em família'
  if (m === 2 || m === '2') return '2 · Unitário'
  return '—'
}

// Mapeia o tipo da campanha para o tipo de parâmetro (ENCARTE / ALERTA / FDS_SAZONAL)
export function tipoParam(tipo) {
  const t = String(tipo || '').toUpperCase()
  if (t.includes('ALERTA')) return 'ALERTA'
  if (t.includes('FDS') || t.includes('SAZ')) return 'FDS_SAZONAL'
  return 'ENCARTE'
}

// Margem % de um item (oferta vs custo)
export function itemMargin(it) {
  const oferta = Number(it.preco_oferta)
  const custo = Number(it.custo)
  if (!oferta || !custo || oferta <= 0 || custo <= 0) return null
  return ((oferta - custo) / oferta) * 100
}

// Margem média de uma lista de itens (ignora itens sem custo/oferta)
export function avgMargin(items) {
  const vals = items.map(itemMargin).filter((v) => v !== null && !Number.isNaN(v))
  if (!vals.length) return null
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

// Agrupa itens por comprador (criado_por) e devolve margem média de cada um
export function marginsByBuyer(items) {
  const byBuyer = {}
  for (const it of items) {
    const dono = (it.criado_por || '').trim() || '—'
    ;(byBuyer[dono] = byBuyer[dono] || []).push(it)
  }
  return Object.entries(byBuyer)
    .map(([dono, its]) => ({ dono, margem: avgMargin(its), qtd: its.length }))
    .sort((a, b) => a.dono.localeCompare(b.dono))
}

export function pct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${v.toFixed(1)}%`
}

// Cor da tag de margem conforme a faixa
export function marginTone(v) {
  if (v === null || v === undefined) return 'faint'
  if (v >= 25) return 'good'
  if (v >= 12) return 'warn'
  return 'bad'
}
