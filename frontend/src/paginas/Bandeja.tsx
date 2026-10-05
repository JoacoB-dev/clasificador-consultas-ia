import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { EtiquetaCategoria, EtiquetaEstado, EtiquetaUrgencia, Sla } from '../componentes/Etiquetas'
import { AREAS, CATEGORIAS, ESTADOS, URGENCIAS, fechaCorta } from '../formato'
import type { ConsultaResumen, Pagina, ResumenBandeja } from '../tipos'

const FILTROS = ['estado', 'categoria', 'urgencia', 'area', 'q', 'sla_vencido'] as const
const TAMANIO = 15

export default function Bandeja() {
  const [params, setParams] = useSearchParams()
  const [datos, setDatos] = useState<Pagina<ConsultaResumen> | null>(null)
  const [resumen, setResumen] = useState<ResumenBandeja | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState(params.get('q') ?? '')
  const pagina = Number(params.get('pagina') ?? '1')

  const cargar = useCallback(() => {
    const query = new URLSearchParams()
    FILTROS.forEach((f) => params.get(f) && query.set(f, params.get(f)!))
    query.set('pagina', String(pagina))
    query.set('tamanio', String(TAMANIO))
    api.get<Pagina<ConsultaResumen>>(`/consultas?${query}`).then(setDatos).catch((e) => setError(e.message))
    api.get<ResumenBandeja>('/metricas/resumen').then(setResumen).catch(() => undefined)
  }, [params, pagina])

  useEffect(() => {
    cargar()
    // Refresco automático: el worker clasifica en segundo plano
    const intervalo = setInterval(cargar, 10000)
    return () => clearInterval(intervalo)
  }, [cargar])

  function cambiarFiltro(nombre: string, valor: string) {
    const nuevos = new URLSearchParams(params)
    if (valor) nuevos.set(nombre, valor)
    else nuevos.delete(nombre)
    nuevos.delete('pagina')
    setParams(nuevos)
  }

  function irAPagina(numero: number) {
    const nuevos = new URLSearchParams(params)
    nuevos.set('pagina', String(numero))
    setParams(nuevos)
  }

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / TAMANIO)) : 1

  return (
    <section>
      <div className="encabezado">
        <div>
          <h1>Bandeja de consultas</h1>
          <p className="sutil">
            Clasificador activo: <code>{resumen?.clasificador_activo ?? '…'}</code>
          </p>
        </div>
        {resumen && (
          <div className="indicadores">
            <div className="indicador">
              <span>{resumen.por_estado.clasificada ?? 0}</span>
              <small>para revisar</small>
            </div>
            <div className="indicador">
              <span>{(resumen.por_estado.pendiente ?? 0) + (resumen.por_estado.en_proceso ?? 0)}</span>
              <small>en cola</small>
            </div>
            <button
              className={`indicador alerta ${params.get('sla_vencido') ? 'activo' : ''}`}
              onClick={() => cambiarFiltro('sla_vencido', params.get('sla_vencido') ? '' : 'true')}
              title="Filtrar las que tienen el SLA vencido"
            >
              <span>{resumen.sla_vencidas}</span>
              <small>SLA vencido</small>
            </button>
          </div>
        )}
      </div>

      <div className="filtros">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            cambiarFiltro('q', busqueda.trim())
          }}
        >
          <input
            type="search"
            placeholder="Buscar en asunto, texto o remitente…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </form>
        <Selector nombre="estado" etiqueta="Estado" opciones={ESTADOS} params={params} onChange={cambiarFiltro} />
        <Selector nombre="categoria" etiqueta="Categoría" opciones={CATEGORIAS} params={params} onChange={cambiarFiltro} />
        <Selector nombre="urgencia" etiqueta="Urgencia" opciones={URGENCIAS} params={params} onChange={cambiarFiltro} />
        <Selector
          nombre="area"
          etiqueta="Área"
          opciones={Object.fromEntries(AREAS.map((a) => [a, a]))}
          params={params}
          onChange={cambiarFiltro}
        />
        {FILTROS.some((f) => params.get(f)) && (
          <button
            className="boton-link"
            onClick={() => {
              setBusqueda('')
              setParams({})
            }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      <div className="tabla-contenedor">
        <table className="tabla">
          <thead>
            <tr>
              <th>#</th>
              <th>Consulta</th>
              <th>Categoría</th>
              <th>Urgencia</th>
              <th>Área</th>
              <th>SLA</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {datos?.items.map((c) => (
              <tr key={c.id} className={c.sla_vencido ? 'fila-vencida' : ''}>
                <td className="sutil">{c.id}</td>
                <td>
                  <Link to={`/consultas/${c.id}`} className="asunto">
                    {c.asunto}
                  </Link>
                  <div className="sutil chico">
                    {c.remitente_nombre ?? c.remitente_email} · {c.canal === 'email' ? '✉ mail' : '🌐 formulario'} ·{' '}
                    {fechaCorta(c.recibida_en)}
                  </div>
                  {c.resumen && <div className="resumen">{c.resumen}</div>}
                </td>
                <td>
                  <EtiquetaCategoria valor={c.categoria} />
                  {c.corregida && <span className="marca-corregida" title="Categoría corregida por una persona">✎</span>}
                </td>
                <td>
                  <EtiquetaUrgencia valor={c.urgencia} />
                </td>
                <td>{c.area_asignada ?? '—'}</td>
                <td>
                  <Sla vence={c.sla_vence_en} vencido={c.sla_vencido} aprobada={c.estado === 'aprobada'} />
                </td>
                <td>
                  <EtiquetaEstado valor={c.estado} />
                </td>
              </tr>
            ))}
            {datos && datos.items.length === 0 && (
              <tr>
                <td colSpan={7} className="vacio">
                  No hay consultas con esos filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {datos && datos.total > TAMANIO && (
        <div className="paginado">
          <button className="boton" disabled={pagina <= 1} onClick={() => irAPagina(pagina - 1)}>
            ← Anterior
          </button>
          <span>
            Página {pagina} de {totalPaginas} ({datos.total} consultas)
          </span>
          <button
            className="boton"
            disabled={pagina >= totalPaginas}
            onClick={() => irAPagina(pagina + 1)}
          >
            Siguiente →
          </button>
        </div>
      )}
    </section>
  )
}

function Selector(props: {
  nombre: string
  etiqueta: string
  opciones: Record<string, string>
  params: URLSearchParams
  onChange: (nombre: string, valor: string) => void
}) {
  return (
    <select
      aria-label={props.etiqueta}
      value={props.params.get(props.nombre) ?? ''}
      onChange={(e) => props.onChange(props.nombre, e.target.value)}
    >
      <option value="">{props.etiqueta}: todas</option>
      {Object.entries(props.opciones).map(([valor, texto]) => (
        <option key={valor} value={valor}>
          {texto}
        </option>
      ))}
    </select>
  )
}
