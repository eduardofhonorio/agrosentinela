import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { api, num, moeda, dataHora } from '../api'
import { Alerta, Kpi, Badge, Carregando, Erro } from '../components/comuns'

const COR_STATUS = { CRITICO: '#d03b3b', ATENCAO: '#fab219', INFO: '#2a78d6', OK: '#0ca30c' }
const FILTROS = [
  { id: 'TODOS', nome: 'Todos' },
  { id: 'CRITICO', nome: 'Críticos' },
  { id: 'ATENCAO', nome: 'Atenção' },
  { id: 'INFO', nome: 'Informativos' },
]

export default function Painel({ onAbrirTalhao, irPara }) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [filtro, setFiltro] = useState('TODOS')
  const [cultura, setCultura] = useState('TODAS')

  useEffect(() => {
    api.get('/api/painel').then(setDados).catch((e) => setErro(e.message))
  }, [])

  const culturas = useMemo(() => [...new Set((dados?.talhoes || []).map((t) => t.cultura))].sort(), [dados])
  const alertas = useMemo(() => (dados?.alertas || []).filter((a) =>
    (filtro === 'TODOS' || a.severidade === filtro) && (cultura === 'TODAS' || a.cultura === cultura)), [dados, filtro, cultura])

  if (erro) return <Erro erro={erro} onIntegrar={() => irPara('integracao')} />
  if (!dados) return <Carregando />
  const k = dados.kpis

  return (
    <>
      <div className="topo">
        <div>
          <h1>Painel de decisão</h1>
          <p>Situação de hoje e próximos 7 dias · atualizado em {dataHora(k.ultima_atualizacao)}</p>
        </div>
      </div>
      {k.cenario && <div className="banner">⚠️ Cenário simulado ativo: <b>{k.cenario}</b> (frente fria aplicada à previsão para demonstração). Rode a integração sem cenário para voltar aos dados reais.</div>}

      <div className="kpis">
        <Kpi rotulo="Talhões monitorados" valor={k.talhoes} detalhe={`${num(k.area_total_ha, 1)} ha · ${k.produtores} produtores`} />
        <Kpi rotulo="Alertas críticos" valor={k.alertas_criticos} detalhe={`+ ${k.alertas_atencao} em atenção`} />
        <Kpi rotulo="Chuva média (30 dias)" valor={`${num(k.chuva_media_30d, 0)} mm`} detalhe={`prevista 7 dias: ${num(k.chuva_prevista_7d, 0)} mm`} />
        <Kpi rotulo="Menor mínima prevista" valor={`${num(k.menor_temp_prevista, 1)} °C`} detalhe="entre todos os talhões" />
        <Kpi rotulo="Custo evitável (30 dias)" valor={moeda(k.custo_evitavel)} detalhe="irrigação em dias de chuva" />
      </div>

      <div className="grid g-painel">
        <div className="card">
          <div className="card-titulo">
            <div><h2>Mapa dos talhões</h2><p>cor = alerta mais grave do talhão · clique para detalhar</p></div>
          </div>
          <div className="mapa">
            <MapContainer center={[-21.85, -46.8]} zoom={9} style={{ height: '100%' }} scrollWheelZoom={false}>
              <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              {dados.talhoes.map((t) => (
                <CircleMarker key={t.talhao_key} center={[t.latitude, t.longitude]}
                  radius={Math.max(8, Math.sqrt(t.area_ha) * 2.2)}
                  pathOptions={{ color: '#fff', weight: 2, fillColor: COR_STATUS[t.status], fillOpacity: 0.9 }}
                  eventHandlers={{ click: () => onAbrirTalhao(t.talhao_key) }}>
                  <Tooltip>
                    <b>{t.codigo} · {t.nome}</b><br />
                    {t.cultura} · {num(t.area_ha, 1)} ha · {t.cidade}<br />
                    Água no solo: {num(t.agua_disponivel_pct, 0)}% · Alertas: {t.qtd_alertas}
                  </Tooltip>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
          <div className="legenda">
            {['CRITICO', 'ATENCAO', 'INFO', 'OK'].map((s) => <span key={s}><Badge sev={s} /></span>)}
            <span>tamanho = área do talhão</span>
          </div>

          <div className="tabela-wrap" style={{ marginTop: 16 }}>
            <table>
              <thead><tr><th>Talhão</th><th>Cultura</th><th className="num">Água solo</th><th className="num">Chuva 30d</th><th className="num">Mín. prev.</th><th>Status</th></tr></thead>
              <tbody>
                {dados.talhoes.map((t) => (
                  <tr key={t.talhao_key} style={{ cursor: 'pointer' }} onClick={() => onAbrirTalhao(t.talhao_key)}>
                    <td><b>{t.codigo}</b> {t.nome}</td>
                    <td>{t.cultura.toLowerCase()}<br /><small style={{ color: '#8a887f' }}>{t.cidade}/{t.uf}</small></td>
                    <td className="num">{num(t.agua_disponivel_pct, 0)}%</td>
                    <td className="num">{num(t.chuva_30d, 0)} mm</td>
                    <td className="num">{num(t.temp_min_prev_7d, 1)} °C</td>
                    <td><Badge sev={t.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-titulo">
            <div><h2>Alertas e recomendações</h2><p>{alertas.length} de {dados.alertas.length} · gerados pela integração</p></div>
            <select value={cultura} onChange={(e) => setCultura(e.target.value)} className="btn">
              <option value="TODAS">Todas as culturas</option>
              {culturas.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="filtros">
            {FILTROS.map((f) => (
              <button key={f.id} className={`chip ${filtro === f.id ? 'ativo' : ''}`} onClick={() => setFiltro(f.id)}>{f.nome}</button>
            ))}
          </div>
          <div className="lista-alertas">
            {alertas.map((a) => <Alerta key={a._id} a={a} onAbrir={onAbrirTalhao} />)}
            {!alertas.length && <div className="vazio">Nenhum alerta para este filtro. 🌤️</div>}
          </div>
        </div>
      </div>
    </>
  )
}
