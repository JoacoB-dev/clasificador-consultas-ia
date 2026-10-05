import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { EtiquetaEstado, EtiquetaUrgencia, Sla } from '../componentes/Etiquetas'
import { CATEGORIAS, URGENCIAS, fechaCorta, porcentaje } from '../formato'
import type { Categoria, ConsultaDetalle, Urgencia } from '../tipos'

const NOMBRES_DATOS: Record<string, string> = {
  numero_pedido: 'Nº de pedido',
  producto: 'Producto',
  monto: 'Monto',
  medio_pago: 'Medio de pago',
  fecha_mencionada: 'Fecha mencionada',
}

export default function Detalle() {
  const { id } = useParams()
  const [c, setC] = useState<ConsultaDetalle | null>(null)
  const [borrador, setBorrador] = useState('')
  const [categoria, setCategoria] = useState<Categoria | ''>('')
  const [urgencia, setUrgencia] = useState<Urgencia | ''>('')
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [guardando, setGuardando] = useState(false)

  function mostrar(d: ConsultaDetalle) {
    setC(d)
    setBorrador(d.borrador_respuesta ?? '')
    setCategoria(d.categoria ?? '')
    setUrgencia(d.urgencia ?? '')
  }

  useEffect(() => {
    api
      .get<ConsultaDetalle>(`/consultas/${id}`)
      .then(mostrar)
      .catch((e) => setMensaje({ tipo: 'error', texto: e.message }))
  }, [id])

  if (!c) return <p>{mensaje?.texto ?? 'Cargando…'}</p>

  const editable = c.estado === 'clasificada'
  const hayCambios =
    borrador !== (c.borrador_respuesta ?? '') || categoria !== (c.categoria ?? '') || urgencia !== (c.urgencia ?? '')

  async function accion(fn: () => Promise<ConsultaDetalle>, ok: string) {
    setGuardando(true)
    setMensaje(null)
    try {
      mostrar(await fn())
      setMensaje({ tipo: 'ok', texto: ok })
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e instanceof Error ? e.message : 'Error' })
    } finally {
      setGuardando(false)
    }
  }

  // Solo mandamos lo que cambió: así cada corrección queda registrada una sola vez
  const enviarCambios = () =>
    api.patch<ConsultaDetalle>(`/consultas/${c.id}`, {
      borrador_respuesta: borrador !== c.borrador_respuesta ? borrador : undefined,
      categoria: categoria !== c.categoria ? categoria : undefined,
      urgencia: urgencia !== c.urgencia ? urgencia : undefined,
    })

  const guardar = () => accion(enviarCambios, 'Cambios guardados')

  const aprobar = () =>
    accion(async () => {
      if (hayCambios) await enviarCambios()
      return api.post<ConsultaDetalle>(`/consultas/${c.id}/aprobar`, { respuesta_final: borrador })
    }, 'Respuesta aprobada')

  const reprocesar = () =>
    accion(async () => {
      await api.post(`/consultas/${c.id}/reprocesar`)
      return api.get<ConsultaDetalle>(`/consultas/${c.id}`)
    }, 'Enviada de nuevo a la cola')

  return (
    <section className="detalle">
      <Link to="/" className="volver">
        ← Volver a la bandeja
      </Link>
      <div className="encabezado">
        <div>
          <h1>
            #{c.id} · {c.asunto}
          </h1>
          <p className="sutil">
            {c.remitente_nombre ? `${c.remitente_nombre} <${c.remitente_email}>` : c.remitente_email} · vía{' '}
            {c.canal} · recibida {fechaCorta(c.recibida_en)}
          </p>
        </div>
        <div className="fila-etiquetas">
          <EtiquetaEstado valor={c.estado} />
          <EtiquetaUrgencia valor={c.urgencia} />
          <Sla vence={c.sla_vence_en} vencido={c.sla_vencido} aprobada={c.estado === 'aprobada'} />
        </div>
      </div>

      {mensaje && <p className={mensaje.tipo === 'ok' ? 'exito' : 'error'}>{mensaje.texto}</p>}

      <div className="grilla-detalle">
        <div className="columna">
          <div className="tarjeta">
            <h2>Mensaje original</h2>
            <pre className="cuerpo">{c.cuerpo}</pre>
          </div>

          <div className="tarjeta">
            <h2>Respuesta al cliente</h2>
            {c.estado === 'aprobada' ? (
              <>
                <pre className="cuerpo">{c.respuesta_final}</pre>
                <p className="sutil chico">Aprobada el {fechaCorta(c.aprobada_en)}. (El envío real del mail no está implementado.)</p>
              </>
            ) : (
              <>
                <textarea
                  rows={9}
                  value={borrador}
                  disabled={!editable}
                  onChange={(e) => setBorrador(e.target.value)}
                  placeholder="El borrador aparece cuando el worker termina de clasificar"
                />
                <div className="acciones">
                  <button className="boton" disabled={!editable || !hayCambios || guardando} onClick={guardar}>
                    Guardar cambios
                  </button>
                  <button className="boton primario" disabled={!editable || guardando || !borrador.trim()} onClick={aprobar}>
                    Aprobar respuesta
                  </button>
                  {(c.estado === 'error' || c.estado === 'clasificada') && (
                    <button className="boton-link" disabled={guardando} onClick={reprocesar}>
                      Reprocesar con el clasificador
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="columna">
          <div className="tarjeta">
            <h2>Clasificación</h2>
            {c.estado === 'error' && <p className="error">Falló la clasificación: {c.error_detalle}</p>}
            {(c.estado === 'pendiente' || c.estado === 'en_proceso') && (
              <p className="sutil">Esperando al worker… (recargá en unos segundos)</p>
            )}
            <label>
              Categoría
              <select value={categoria} disabled={!editable} onChange={(e) => setCategoria(e.target.value as Categoria)}>
                {!c.categoria && <option value="">—</option>}
                {Object.entries(CATEGORIAS).map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            {c.categoria_modelo && c.categoria_modelo !== c.categoria && (
              <p className="nota">
                El modelo había dicho <strong>{CATEGORIAS[c.categoria_modelo]}</strong> (corregido)
              </p>
            )}
            <label>
              Urgencia
              <select value={urgencia} disabled={!editable} onChange={(e) => setUrgencia(e.target.value as Urgencia)}>
                {!c.urgencia && <option value="">—</option>}
                {Object.entries(URGENCIAS).map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <dl className="datos">
              <dt>Área asignada</dt>
              <dd>{c.area_asignada ?? '—'}</dd>
              <dt>Sentimiento</dt>
              <dd>{c.sentimiento ?? '—'}</dd>
              <dt>Confianza</dt>
              <dd>{porcentaje(c.confianza)}</dd>
              <dt>Clasificador</dt>
              <dd>
                <code>{c.clasificador ?? '—'}</code>
              </dd>
              <dt>Resumen</dt>
              <dd>{c.resumen ?? '—'}</dd>
            </dl>
          </div>

          {c.datos_extraidos && (
            <div className="tarjeta">
              <h2>Datos extraídos</h2>
              <dl className="datos">
                {Object.keys(NOMBRES_DATOS).map((k) => [k, c.datos_extraidos?.[k] ?? null] as const).map(([k, v]) => (
                  <div key={k} className="par">
                    <dt>{NOMBRES_DATOS[k] ?? k}</dt>
                    <dd>{v === null ? <span className="sutil">no figura</span> : String(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {c.reglas_aplicadas && c.reglas_aplicadas.length > 0 && (
            <div className="tarjeta">
              <h2>Reglas de negocio aplicadas</h2>
              <ul className="reglas">
                {c.reglas_aplicadas.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {c.correcciones.length > 0 && (
            <div className="tarjeta">
              <h2>Historial de correcciones</h2>
              <ul className="reglas">
                {c.correcciones.map((x) => (
                  <li key={x.id}>
                    {fechaCorta(x.creada_en)}: {x.campo} <s>{x.valor_anterior}</s> → <strong>{x.valor_nuevo}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
