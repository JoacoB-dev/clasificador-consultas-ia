import { useEffect, useState } from 'react'
import { api } from '../api'
import { CATEGORIAS, porcentaje, usd } from '../formato'
import type { Categoria, MetricasPrecision, MetricasUso } from '../tipos'

export default function Metricas() {
  const [precision, setPrecision] = useState<MetricasPrecision | null>(null)
  const [uso, setUso] = useState<MetricasUso | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<MetricasPrecision>('/metricas/precision').then(setPrecision).catch((e) => setError(e.message))
    api.get<MetricasUso>('/metricas/uso-llm').then(setUso).catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!precision || !uso) return <p>Cargando…</p>

  const categorias = precision.por_categoria.map((p) => p.categoria)
  const celda = (modelo: Categoria, real: Categoria) =>
    precision.matriz_confusion.find((m) => m.modelo === modelo && m.real === real)?.cantidad ?? 0

  return (
    <section>
      <div className="encabezado">
        <div>
          <h1>Métricas del clasificador</h1>
          <p className="sutil">
            Se calculan sobre las consultas que una persona revisó (aprobó o corrigió). Cada corrección de categoría
            cuenta como un error del modelo.
          </p>
        </div>
      </div>

      <div className="indicadores grandes">
        <div className="indicador">
          <span>{porcentaje(precision.exactitud)}</span>
          <small>exactitud global</small>
        </div>
        <div className="indicador">
          <span>{precision.total_revisadas}</span>
          <small>consultas revisadas</small>
        </div>
        <div className="indicador">
          <span>{precision.total_revisadas - precision.correctas}</span>
          <small>corregidas</small>
        </div>
      </div>

      <div className="tarjeta">
        <h2>Precisión por categoría</h2>
        <table className="tabla compacta">
          <thead>
            <tr>
              <th>Categoría</th>
              <th title="Veces que el modelo eligió la categoría">Predichas</th>
              <th title="De esas, cuántas confirmó una persona">Correctas</th>
              <th>Precisión</th>
              <th title="De las que realmente eran de esta categoría, cuántas detectó">Recall</th>
            </tr>
          </thead>
          <tbody>
            {precision.por_categoria.map((p) => (
              <tr key={p.categoria}>
                <td>{CATEGORIAS[p.categoria]}</td>
                <td>{p.predichas}</td>
                <td>{p.correctas}</td>
                <td>
                  <div className="barra-medida" aria-label={`Precisión ${porcentaje(p.precision)}`}>
                    <div className="relleno" style={{ width: `${(p.precision ?? 0) * 100}%` }} />
                    <span>{porcentaje(p.precision)}</span>
                  </div>
                </td>
                <td>{porcentaje(p.recall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="tarjeta">
        <h2>Matriz de confusión</h2>
        <p className="sutil chico">Filas: lo que dijo el modelo. Columnas: la categoría final después de la revisión.</p>
        <div className="tabla-contenedor">
          <table className="tabla matriz">
            <thead>
              <tr>
                <th>Modelo ↓ / Real →</th>
                {categorias.map((c) => (
                  <th key={c}>{CATEGORIAS[c]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categorias.map((m) => (
                <tr key={m}>
                  <th>{CATEGORIAS[m]}</th>
                  {categorias.map((r) => {
                    const n = celda(m, r)
                    return (
                      <td key={r} className={n === 0 ? 'cero' : m === r ? 'acierto' : 'fallo'}>
                        {n}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="tarjeta">
        <h2>Uso del LLM</h2>
        {uso.llamadas === 0 ? (
          <p className="sutil">
            Todavía no hay llamadas registradas. Sin <code>ANTHROPIC_API_KEY</code> se usa el clasificador simulado, que no
            consume tokens.
          </p>
        ) : (
          <>
            <div className="indicadores">
              <div className="indicador">
                <span>{uso.llamadas}</span>
                <small>llamadas</small>
              </div>
              <div className="indicador">
                <span>{(uso.tokens_entrada + uso.tokens_salida).toLocaleString('es-AR')}</span>
                <small>tokens</small>
              </div>
              <div className="indicador">
                <span>{usd(uso.costo_total_usd)}</span>
                <small>costo estimado</small>
              </div>
            </div>
            <table className="tabla compacta">
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Llamadas</th>
                  <th>Fallidas</th>
                  <th>Tokens entrada</th>
                  <th>Tokens salida</th>
                  <th>Costo</th>
                  <th>Duración prom.</th>
                </tr>
              </thead>
              <tbody>
                {uso.por_modelo.map((m) => (
                  <tr key={m.modelo}>
                    <td>
                      <code>{m.modelo}</code>
                    </td>
                    <td>{m.llamadas}</td>
                    <td>{m.fallidas}</td>
                    <td>{m.tokens_entrada.toLocaleString('es-AR')}</td>
                    <td>{m.tokens_salida.toLocaleString('es-AR')}</td>
                    <td>{usd(m.costo_usd)}</td>
                    <td>{(m.duracion_promedio_ms / 1000).toFixed(1)} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </section>
  )
}
