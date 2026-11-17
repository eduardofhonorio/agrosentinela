import { useEffect, useRef, useState } from 'react'
import { api, dataHora } from '../api'

function Fluxo() {
  const col = (titulo, itens) => (
    <div className="fluxo-col">
      <h3>{titulo}</h3>
      {itens.map(([b, s]) => <div className="fluxo-item" key={b}><b>{b}</b><small>{s}</small></div>)}
    </div>
  )
  return (
    <div className="fluxo">
      {col('Fontes', [['MySQL', 'ERP: cadastro e operações'], ['SQLite', 'caderno de campo offline'], ['API Open-Meteo', 'histórico + previsão'], ['API ViaCEP', 'CEP → endereço/IBGE']])}
      <div className="fluxo-seta">➜</div>
      {col('Integração', [['Apache Hop', 'pipeline REST → JSON → MySQL'], ['Python (pandas)', 'limpeza, junção, regras'], ['Workflow Hop', 'orquestração diária']])}
      <div className="fluxo-seta">➜</div>
      {col('Armazenamento', [['DuckDB', 'Data Warehouse estrela'], ['MongoDB', 'alertas, JSON bruto, logs']])}
      <div className="fluxo-seta">➜</div>
      {col('Entrega', [['FastAPI', 'API REST /api/...'], ['React', 'painel, mapa, gráficos']])}
    </div>
  )
}

export default function Integracao() {
  const [saude, setSaude] = useState(null)
  const [execs, setExecs] = useState([])
  const [estado, setEstado] = useState(null)
  const [rejeitados, setRejeitados] = useState([])
  const [amostras, setAmostras] = useState(null)
  const [cenario, setCenario] = useState('')
  const [erro, setErro] = useState(null)
  const timer = useRef(null)

  const carregar = () => {
    api.get('/api/saude').then(setSaude).catch((e) => setErro(e.message))
    api.get('/api/etl/execucoes').then(setExecs).catch(() => {})
    api.get('/api/etl/rejeitados').then(setRejeitados).catch(() => {})
    api.get('/api/etl/amostras').then(setAmostras).catch(() => {})
  }
  const acompanhar = () => {
    clearInterval(timer.current)
    timer.current = setInterval(async () => {
      const s = await api.get('/api/etl/status')
      setEstado(s)
      if (!s.executando) { clearInterval(timer.current); carregar() }
    }, 1000)
  }
  useEffect(() => {
    carregar()
    api.get('/api/etl/status').then((s) => { setEstado(s); if (s.executando) acompanhar() })
    return () => clearInterval(timer.current)
  }, [])

  const executar = async () => {
    setErro(null)
    try {
      await api.post(`/api/etl/executar${cenario ? `?cenario=${cenario}` : ''}`)
      setEstado({ executando: true, log: [] })
      acompanhar()
    } catch (e) { setErro(e.message) }
  }

  const ultima = execs[0]
  return (
    <>
      <div className="topo">
        <div><h1>Integração de dados</h1><p>Pipeline que coleta, limpa, integra e consolida as fontes</p></div>
        <div className="topo-acoes">
          <select className="btn" value={cenario} onChange={(e) => setCenario(e.target.value)}>
            <option value="">Dados reais</option>
            <option value="geada">Simular frente fria (demo)</option>
          </select>
          <button className="btn btn-primario" onClick={executar} disabled={estado?.executando}>
            {estado?.executando ? '⏳ Executando...' : '▶ Executar integração'}
          </button>
        </div>
      </div>
      {erro && <div className="aviso erro" style={{ marginBottom: 16 }}>{erro}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-titulo"><div><h2>Arquitetura</h2><p>motor de coleta: {saude?.apache_hop || '...'}</p></div>
          <div className="filtros" style={{ margin: 0 }}>
            {saude && Object.entries(saude.bancos).map(([b, s]) => (
              <span key={b} className={`badge ${s === 'ok' ? 'sev-OK' : 'sev-ATENCAO'}`} title={s}>{b}: {s === 'ok' ? 'conectado' : s}</span>
            ))}
          </div>
        </div>
        <Fluxo />
      </div>

      <div className="grid g2">
        <div className="card">
          <div className="card-titulo"><div><h2>Execução</h2><p>{estado?.inicio ? `iniciada em ${dataHora(estado.inicio)}` : 'acompanhe o log em tempo real'}</p></div></div>
          <div className="log">{estado?.log?.length ? estado.log.join('\n') : 'Nenhuma execução nesta sessão. Clique em "Executar integração".'}</div>
          {ultima && (
            <>
              <h3 style={{ margin: '16px 0 6px' }}>Última execução registrada no MongoDB · {ultima.status} em {ultima.duracao_s}s{ultima.cenario ? ` · cenário ${ultima.cenario}` : ''}</h3>
              {ultima.etapas.map((e) => (
                <div className="etapa" key={e.etapa}>
                  <span>{e.etapa}<br /><small>{typeof e.detalhes === 'string' ? e.detalhes : Object.entries(e.detalhes).filter(([k]) => !['transforms', 'erros'].includes(k)).map(([k, v]) => `${k}: ${typeof v === 'object' && v ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(', ') : v}`).join(' · ')}</small></span>
                  <small>{e.duracao_s}s</small>
                </div>
              ))}
              {ultima.erro && <div className="aviso erro" style={{ marginTop: 8 }}>{ultima.erro}</div>}
            </>
          )}
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Histórico</h2><p>coleção execucoes_etl (MongoDB)</p></div></div>
          <table>
            <thead><tr><th>Início</th><th>Status</th><th className="num">Duração</th><th>Coleta</th></tr></thead>
            <tbody>{execs.map((x) => (
              <tr key={x._id}><td>{dataHora(x.inicio)}</td>
                <td><span className={`badge ${x.status === 'SUCESSO' ? 'sev-OK' : 'sev-CRITICO'}`}>{x.status}</span>{x.cenario && <small> ({x.cenario})</small>}</td>
                <td className="num">{x.duracao_s}s</td><td>{x.etapas?.[0]?.detalhes?.motor || '–'}</td></tr>))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Registros rejeitados na limpeza</h2><p>{rejeitados.length} registros do caderno de campo (SQLite) não passaram na validação</p></div></div>
          <div className="tabela-wrap" style={{ maxHeight: 320, overflow: 'auto' }}>
            <table>
              <thead><tr><th>Origem</th><th>Motivo</th><th>Registro original</th></tr></thead>
              <tbody>{rejeitados.map((r) => (
                <tr key={r._id}><td>{r.origem}</td><td>{r.motivo}</td>
                  <td><code style={{ fontSize: 11 }}>{r.registro.talhao} | {r.registro.data_leitura || r.registro.data_obs} | {r.registro.milimetros ?? r.registro.praga} {r.registro.nivel !== undefined && r.registro.nivel !== null ? `| nível ${r.registro.nivel}` : ''}</code></td></tr>))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-titulo"><div><h2>Dados brutos (antes da integração)</h2><p>guardados no MongoDB para auditoria e reprocessamento</p></div></div>
          <h3 style={{ marginBottom: 6 }}>Caderno de campo (SQLite) - repare nos formatos misturados</h3>
          <div className="json" style={{ maxHeight: 150, marginBottom: 12 }}>{amostras ? JSON.stringify(amostras.caderno_campo.slice(0, 6), null, 1) : '...'}</div>
          <h3 style={{ marginBottom: 6 }}>Resposta da API Open-Meteo (recorte)</h3>
          <div className="json">{amostras?.open_meteo ? JSON.stringify(amostras.open_meteo.resposta, null, 2) : 'Disponível após uma coleta pelo coletor Python.'}</div>
        </div>
      </div>
    </>
  )
}
