import { useEffect, useState } from 'react'
import { api, num } from '../api'

const PROP_VAZIA = { produtor_id: '', nome: '', cep: '', logradouro: '', bairro: '', cidade: '', uf: '', ibge: '', latitude: '', longitude: '' }
const TALHAO_VAZIO = { propriedade_id: '', codigo: '', nome: '', cultura_id: '', area_ha: '', data_plantio: '', irrigado: false }

export default function Cadastro({ irPara }) {
  const [op, setOp] = useState(null)
  const [msg, setMsg] = useState(null)
  const [produtor, setProdutor] = useState({ nome: '', telefone: '', email: '' })
  const [prop, setProp] = useState(PROP_VAZIA)
  const [talhao, setTalhao] = useState(TALHAO_VAZIO)
  const [buscandoCep, setBuscandoCep] = useState(false)
  const [cepInfo, setCepInfo] = useState(null)

  const carregar = () => api.get('/api/cadastro/opcoes').then(setOp).catch((e) => setMsg({ tipo: 'erro', texto: e.message }))
  useEffect(() => { carregar() }, [])

  const buscarCep = async () => {
    setBuscandoCep(true); setCepInfo(null)
    try {
      const r = await api.get(`/api/cep/${prop.cep}`)
      setProp((p) => ({ ...p, cep: r.cep, logradouro: r.logradouro || p.logradouro, bairro: r.bairro || p.bairro, cidade: r.cidade, uf: r.uf, ibge: r.ibge, latitude: r.latitude, longitude: r.longitude }))
      setCepInfo({ tipo: 'ok', texto: `Endereço via ViaCEP e coordenadas via Open-Meteo Geocoding (${num(r.latitude, 4)}, ${num(r.longitude, 4)}${r.elevacao ? `, altitude ${num(r.elevacao, 0)} m` : ''}).` })
    } catch (e) {
      setCepInfo({ tipo: 'erro', texto: e.message })
    } finally { setBuscandoCep(false) }
  }

  const enviar = async (rota, dados, limpar, texto) => {
    setMsg(null)
    try {
      await api.post(rota, dados)
      limpar()
      await carregar()
      setMsg({ tipo: 'ok', texto })
    } catch (e) { setMsg({ tipo: 'erro', texto: e.message }) }
  }

  if (!op) return <div className="vazio">{msg?.texto || 'Carregando...'}</div>
  const campo = (obj, set, k) => ({ value: obj[k], onChange: (e) => set({ ...obj, [k]: e.target.value }) })

  return (
    <>
      <div className="topo">
        <div><h1>Cadastro</h1><p>Dados gravados no MySQL (sistema transacional). O endereço é enriquecido por APIs externas.</p></div>
      </div>
      {msg && <div className={`aviso ${msg.tipo}`} style={{ marginBottom: 16 }}>
        {msg.texto} {msg.tipo === 'ok' && <a href="#" onClick={(e) => { e.preventDefault(); irPara('integracao') }}>Executar integração →</a>}
      </div>}

      <div className="grid g3">
        <div className="card">
          <h2 style={{ marginBottom: 12 }}>1. Produtor</h2>
          <form className="form" onSubmit={(e) => { e.preventDefault(); enviar('/api/cadastro/produtores', produtor, () => setProdutor({ nome: '', telefone: '', email: '' }), 'Produtor cadastrado.') }}>
            <label>Nome<input required minLength={3} {...campo(produtor, setProdutor, 'nome')} /></label>
            <label>Telefone<input {...campo(produtor, setProdutor, 'telefone')} placeholder="(19) 99999-0000" /></label>
            <label>E-mail<input type="email" {...campo(produtor, setProdutor, 'email')} /></label>
            <button className="btn btn-primario">Salvar produtor</button>
          </form>
        </div>

        <div className="card">
          <h2 style={{ marginBottom: 12 }}>2. Propriedade</h2>
          <form className="form" onSubmit={(e) => {
            e.preventDefault()
            enviar('/api/cadastro/propriedades', { ...prop, produtor_id: Number(prop.produtor_id), latitude: Number(prop.latitude), longitude: Number(prop.longitude) },
              () => { setProp(PROP_VAZIA); setCepInfo(null) }, 'Propriedade cadastrada.')
          }}>
            <label>Produtor<select required {...campo(prop, setProp, 'produtor_id')}>
              <option value="">Selecione...</option>{op.produtores.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </select></label>
            <label>Nome da propriedade<input required minLength={3} {...campo(prop, setProp, 'nome')} /></label>
            <div className="linha-form" style={{ alignItems: 'end' }}>
              <label>CEP<input required {...campo(prop, setProp, 'cep')} placeholder="13870-431" /></label>
              <button type="button" className="btn" onClick={buscarCep} disabled={buscandoCep}>{buscandoCep ? 'Buscando...' : '🔎 Buscar CEP'}</button>
            </div>
            {cepInfo && <div className={`aviso ${cepInfo.tipo}`}>{cepInfo.texto}</div>}
            <label>Logradouro<input {...campo(prop, setProp, 'logradouro')} /></label>
            <div className="linha-form">
              <label>Cidade<input required {...campo(prop, setProp, 'cidade')} /></label>
              <label>UF<input required maxLength={2} {...campo(prop, setProp, 'uf')} /></label>
            </div>
            <div className="linha-form">
              <label>Latitude<input required type="number" step="any" {...campo(prop, setProp, 'latitude')} /></label>
              <label>Longitude<input required type="number" step="any" {...campo(prop, setProp, 'longitude')} /></label>
            </div>
            <button className="btn btn-primario">Salvar propriedade</button>
          </form>
        </div>

        <div className="card">
          <h2 style={{ marginBottom: 12 }}>3. Talhão</h2>
          <form className="form" onSubmit={(e) => {
            e.preventDefault()
            enviar('/api/cadastro/talhoes', { ...talhao, propriedade_id: Number(talhao.propriedade_id), cultura_id: Number(talhao.cultura_id), area_ha: Number(talhao.area_ha), data_plantio: talhao.data_plantio || null },
              () => setTalhao(TALHAO_VAZIO), 'Talhão cadastrado. Execute a integração para coletar o clima e gerar os indicadores.')
          }}>
            <label>Propriedade<select required {...campo(talhao, setTalhao, 'propriedade_id')}>
              <option value="">Selecione...</option>{op.propriedades.map((p) => <option key={p.id} value={p.id}>{p.nome} ({p.cidade}/{p.uf})</option>)}
            </select></label>
            <div className="linha-form">
              <label>Código<input required pattern="[A-Za-z]{3}-[0-9]{2}" title="Formato AAA-00" {...campo(talhao, setTalhao, 'codigo')} placeholder="SJB-03" /></label>
              <label>Área (ha)<input required type="number" step="0.01" min="0.01" {...campo(talhao, setTalhao, 'area_ha')} /></label>
            </div>
            <label>Nome<input required minLength={3} {...campo(talhao, setTalhao, 'nome')} /></label>
            <label>Cultura<select required {...campo(talhao, setTalhao, 'cultura_id')}>
              <option value="">Selecione...</option>{op.culturas.map((c) => <option key={c.id} value={c.id}>{c.nome} (Kc {c.kc}, geada {c.temp_geada} °C)</option>)}
            </select></label>
            <label>Data de plantio<input type="date" {...campo(talhao, setTalhao, 'data_plantio')} /></label>
            <label className="check"><input type="checkbox" checked={talhao.irrigado} onChange={(e) => setTalhao({ ...talhao, irrigado: e.target.checked })} /> Talhão irrigado</label>
            <button className="btn btn-primario">Salvar talhão</button>
            <span className="fontes">As coordenadas são herdadas da propriedade.</span>
          </form>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-titulo"><div><h2>Talhões cadastrados no MySQL</h2><p>{op.talhoes.length} talhões</p></div></div>
        <div className="tabela-wrap">
          <table>
            <thead><tr><th>Código</th><th>Nome</th><th>Cultura</th><th>Propriedade</th><th>Cidade</th><th className="num">Área</th><th>Irrigado</th></tr></thead>
            <tbody>{op.talhoes.map((t) => (
              <tr key={t.id}><td><b>{t.codigo}</b></td><td>{t.nome}</td><td>{t.cultura}</td><td>{t.propriedade}</td><td>{t.cidade}</td><td className="num">{num(t.area_ha, 1)} ha</td><td>{t.irrigado ? 'Sim' : 'Não'}</td></tr>))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
