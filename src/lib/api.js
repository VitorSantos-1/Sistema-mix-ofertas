// Cliente REST — todas as chamadas enviam o header x-usuario (o backend usa em get_actor).
const BASE = '/api'

export function getAuthUser() {
  try { return JSON.parse(localStorage.getItem('auth_user') || 'null') } catch { return null }
}
function currentUsuario() {
  const u = getAuthUser()
  return (u && u.usuario) || ''
}

async function req(path, method = 'GET', body) {
  const headers = { 'x-usuario': currentUsuario() }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail
    try { const d = await res.json(); detail = d.detail || d.message } catch { /* ignore */ }
    throw new Error(detail || `Erro ${res.status}`)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res
}

export const api = {
  // Auth / usuários
  login: (usuario, senha) => req('/auth/login', 'POST', { usuario, senha }),
  listUsers: () => req('/auth/usuarios'),
  createUser: (u) => req('/auth/usuarios', 'POST', u),
  updateUser: (usuario, u) => req(`/auth/usuarios/${encodeURIComponent(usuario)}`, 'PUT', u),
  setPassword: (usuario, senha) => req(`/auth/usuarios/${encodeURIComponent(usuario)}/senha`, 'PUT', { senha }),

  // Produtos (catálogo)
  searchProducts: (search = '', limit = 50) =>
    req(`/produtos?search=${encodeURIComponent(search)}&limit=${limit}`),
  getProduct: async (codigo) => { try { return await req(`/produtos/${encodeURIComponent(codigo)}`) } catch { return null } },
  ultimaOferta: async (codigo, excludeId) => { try { return await req(`/produtos/${encodeURIComponent(codigo)}/ultima-oferta?exclude=${encodeURIComponent(excludeId || '')}`) } catch { return null } },
  saveProduct: (p) => req('/produtos', 'POST', p),
  importProducts: (produtos) => req('/produtos/importar-lote', 'POST', { produtos }),

  // Campanhas
  listCampaigns: (params = {}) => req(`/campanhas?${new URLSearchParams(params)}`),
  getCampaign: (id) => req(`/campanhas/${id}`),
  getContexto: (id, usuario) => req(`/campanhas/${id}/contexto?usuario=${encodeURIComponent(usuario || currentUsuario())}`),
  createCampaign: (c) => req('/campanhas', 'POST', c),
  updateCampaign: (id, c) => req(`/campanhas/${id}`, 'PUT', c),
  deleteCampaign: (id) => req(`/campanhas/${id}`, 'DELETE'),
  duplicateCampaign: (id) => req(`/campanhas/${id}/duplicar`, 'POST'),
  archiveOld: (dias = 30) => req('/campanhas/manutencao/arquivar-antigas', 'POST', { dias }),
  checarConflito: (codigo, campanha_id) =>
    req(`/campanhas/conflitos/verificar?codigo=${encodeURIComponent(codigo)}&campanha_id=${encodeURIComponent(campanha_id || '')}`),
  getComparativo: async (id, compare) => { try { return await req(`/campanhas/${id}/comparativo${compare ? `?compare=${encodeURIComponent(compare)}` : ''}`) } catch { return null } },

  // Parâmetros
  getParametros: () => req('/parametros'),
  createParametro: (p) => req('/parametros', 'POST', p),
  updateParametro: (id, p) => req(`/parametros/${id}`, 'PUT', p),
  deleteParametro: (id) => req(`/parametros/${id}`, 'DELETE'),
  updatePool: (tipo, p) => req(`/parametros/pool/${encodeURIComponent(tipo)}`, 'PUT', p),
  // Tipos de campanha (editáveis)
  createTipo: (p) => req('/parametros/tipos', 'POST', p),
  renameTipo: (tipo, novo_nome) => req(`/parametros/tipos/${encodeURIComponent(tipo)}/rename`, 'POST', { novo_nome }),
  deleteTipo: (tipo) => req(`/parametros/tipos/${encodeURIComponent(tipo)}`, 'DELETE'),

  // Exportação
  excelUrl: (id, params = {}) => {
    const q = new URLSearchParams(params).toString()
    return `${BASE}/exportar/excel/${id}${q ? `?${q}` : ''}`
  },

  // Notificações
  getNotificacoes: (usuario) => req(`/notificacoes?nao_lidas=1&usuario=${encodeURIComponent(usuario)}`),
  marcarLida: (nid) => req(`/notificacoes/${nid}/lida`, 'POST'),
  marcarTodasLidas: (usuario) => req(`/notificacoes/marcar-todas-lidas?usuario=${encodeURIComponent(usuario)}`, 'POST'),
}
