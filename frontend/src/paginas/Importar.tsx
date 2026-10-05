import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { ResultadoImportacion } from '../tipos'

const EJEMPLO_JSON = `[
  {
    "nombre": "Juana Pérez",
    "email": "juana@ejemplo.com",
    "asunto": "No me llegó el pedido",
    "cuerpo": "Hola, el pedido 105300 figura entregado pero no lo recibí.",
    "id_externo": "<juana-001@ejemplo.com>"
  }
]`

export default function Importar() {
  const [archivos, setArchivos] = useState<FileList | null>(null)
  const [json, setJson] = useState(EJEMPLO_JSON)
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function ejecutar(fn: () => Promise<ResultadoImportacion>) {
    setEnviando(true)
    setError(null)
    setResultado(null)
    try {
      setResultado(await fn())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    } finally {
      setEnviando(false)
    }
  }

  function subirEml(e: FormEvent) {
    e.preventDefault()
    if (!archivos?.length) return
    const datos = new FormData()
    Array.from(archivos).forEach((a) => datos.append('archivos', a))
    ejecutar(() => api.post<ResultadoImportacion>('/ingreso/eml', datos))
  }

  function subirJson(e: FormEvent) {
    e.preventDefault()
    let lote: unknown
    try {
      lote = JSON.parse(json)
    } catch {
      setError('El texto no es un JSON válido')
      return
    }
    ejecutar(() => api.post<ResultadoImportacion>('/ingreso/json', lote))
  }

  return (
    <section>
      <div className="encabezado">
        <div>
          <h1>Importar consultas</h1>
          <p className="sutil">
            Simula el canal de mail: no hay conexión a una casilla real. Las consultas importadas pasan por la misma
            cola que las del formulario. Los mails con el mismo Message-ID no se duplican.
          </p>
        </div>
      </div>

      <div className="grilla-detalle">
        <form className="tarjeta" onSubmit={subirEml}>
          <h2>Archivos .eml</h2>
          <p className="sutil chico">
            Hay ejemplos en <code>backend/ejemplos/emails/</code>.
          </p>
          <input type="file" accept=".eml,message/rfc822" multiple onChange={(e) => setArchivos(e.target.files)} />
          <div className="acciones">
            <button className="boton primario" disabled={enviando || !archivos?.length}>
              Importar mails
            </button>
          </div>
        </form>

        <form className="tarjeta" onSubmit={subirJson}>
          <h2>Lote JSON</h2>
          <textarea rows={11} value={json} onChange={(e) => setJson(e.target.value)} className="mono" />
          <div className="acciones">
            <button className="boton primario" disabled={enviando}>
              Importar JSON
            </button>
          </div>
        </form>
      </div>

      {error && <p className="error">{error}</p>}
      {resultado && (
        <div className="tarjeta">
          <h2>Resultado</h2>
          <p>
            {resultado.creadas.length} creadas · {resultado.duplicadas} duplicadas · {resultado.errores.length} con
            error
          </p>
          {resultado.creadas.some((c) => !c.encolada) && (
            <p className="error">Algunas no se pudieron encolar (¿Redis caído?). Quedaron pendientes.</p>
          )}
          <ul className="reglas">
            {resultado.creadas.map((c) => (
              <li key={c.id}>
                <Link to={`/consultas/${c.id}`}>Consulta #{c.id}</Link> — {c.estado}
              </li>
            ))}
            {resultado.errores.map((e) => (
              <li key={e} className="error">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
