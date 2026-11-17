// Cliente simples para a API FastAPI (o Vite repassa /api para http://localhost:8000)
async function req(caminho, opcoes = {}) {
  const r = await fetch(caminho, {
    headers: { 'Content-Type': 'application/json' },
    ...opcoes,
  })
  const corpo = await r.json().catch(() => ({}))
  if (!r.ok) {
    const det = corpo.detail
    const msg = Array.isArray(det) ? det.map((d) => `${d.loc?.slice(-1)}: ${d.msg}`).join('; ') : det
    throw new Error(msg || `Erro ${r.status}`)
  }
  return corpo
}

export const api = {
  get: (c) => req(c),
  post: (c, dados) => req(c, { method: 'POST', body: dados ? JSON.stringify(dados) : undefined }),
}

// ---------- formatação pt-BR ----------
export const num = (v, casas = 1) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '–'
    : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

export const moeda = (v) =>
  Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export const dataCurta = (iso) => {
  if (!iso) return ''
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}`
}

export const dataHora = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR') : '–')

export const diaSemana = (iso) =>
  new Date(iso.slice(0, 10) + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')

export const hojeISO = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export const COR = { s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s4: '#eda100', critical: '#d03b3b', good: '#0ca30c', warning: '#fab219', grid: '#e9e7df', eixo: '#8a887f' }

export const ROTULO_SEV = { CRITICO: 'Crítico', ATENCAO: 'Atenção', INFO: 'Info', OK: 'Normal' }
export const ICONE_TIPO = {
  GEADA: '❄️', DEFICIT_HIDRICO: '💧', EXCESSO_CHUVA: '🌧️', DOENCA: '🍂', PRAGA: '🐛', EFICIENCIA: '💰', PULVERIZACAO: '🧪',
}
