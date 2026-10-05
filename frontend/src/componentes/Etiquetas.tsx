import { CATEGORIAS, ESTADOS, URGENCIAS, textoSla } from '../formato'
import type { Categoria, Estado, Urgencia } from '../tipos'

export function EtiquetaUrgencia({ valor }: { valor: Urgencia | null }) {
  if (!valor) return <span className="etiqueta">—</span>
  return <span className={`etiqueta urgencia-${valor}`}>{URGENCIAS[valor]}</span>
}

export function EtiquetaEstado({ valor }: { valor: Estado }) {
  return <span className={`etiqueta estado-${valor}`}>{ESTADOS[valor]}</span>
}

export function EtiquetaCategoria({ valor }: { valor: Categoria | null }) {
  return <span className="etiqueta categoria">{valor ? CATEGORIAS[valor] : 'Sin clasificar'}</span>
}

export function Sla({ vence, vencido, aprobada }: { vence: string | null; vencido: boolean; aprobada: boolean }) {
  if (aprobada) return <span className="sla ok">Respondida</span>
  return <span className={`sla ${vencido ? 'vencido' : ''}`}>{textoSla(vence)}</span>
}
