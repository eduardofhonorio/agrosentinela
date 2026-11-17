import { useState } from 'react'
import Painel from './pages/Painel.jsx'
import Talhao from './pages/Talhao.jsx'
import Analises from './pages/Analises.jsx'
import Cadastro from './pages/Cadastro.jsx'
import Integracao from './pages/Integracao.jsx'

const PAGINAS = [
  { id: 'painel', nome: 'Painel', icone: '🗺️' },
  { id: 'talhao', nome: 'Talhões', icone: '🌱' },
  { id: 'analises', nome: 'Análises', icone: '📊' },
  { id: 'cadastro', nome: 'Cadastro', icone: '📝' },
  { id: 'integracao', nome: 'Integração', icone: '🔄' },
]

export default function App() {
  const [pagina, setPagina] = useState('painel')
  const [talhaoId, setTalhaoId] = useState(null)

  const abrirTalhao = (id) => { setTalhaoId(id); setPagina('talhao') }
  const irPara = (p) => setPagina(p)

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">🌱</div>
          <div><b>AgroSentinela</b><small>inteligência climática no campo</small></div>
        </div>
        {PAGINAS.map((p) => (
          <button key={p.id} className={`nav-btn ${pagina === p.id ? 'ativo' : ''}`} onClick={() => setPagina(p.id)}>
            <span>{p.icone}</span>{p.nome}
          </button>
        ))}
        <div className="sidebar-rodape">
          Fontes: MySQL · SQLite · Open-Meteo · ViaCEP<br />
          Integração: Apache Hop + Python<br />
          Destino: DuckDB (DW) · MongoDB
        </div>
      </aside>
      <main className="main">
        {pagina === 'painel' && <Painel onAbrirTalhao={abrirTalhao} irPara={irPara} />}
        {pagina === 'talhao' && <Talhao talhaoId={talhaoId} setTalhaoId={setTalhaoId} irPara={irPara} />}
        {pagina === 'analises' && <Analises irPara={irPara} />}
        {pagina === 'cadastro' && <Cadastro irPara={irPara} />}
        {pagina === 'integracao' && <Integracao />}
      </main>
    </div>
  )
}
