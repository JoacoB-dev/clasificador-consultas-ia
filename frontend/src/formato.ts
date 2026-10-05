// Funciones puras de presentación (tienen tests en formato.test.ts)
import type { Categoria, Estado, Urgencia } from './tipos'

export const CATEGORIAS: Record<Categoria, string> = {
  envio: 'Envío',
  producto_defectuoso: 'Producto defectuoso',
  devolucion: 'Cambio / devolución',
  facturacion: 'Facturación',
  consulta_producto: 'Consulta de producto',
  cuenta: 'Cuenta',
  otro: 'Otro',
}

export const URGENCIAS: Record<Urgencia, string> = {
  baja: 'Baja',
  media: 'Media',
  alta: 'Alta',
  critica: 'Crítica',
}

export const ESTADOS: Record<Estado, string> = {
  pendiente: 'Pendiente',
  en_proceso: 'En proceso',
  clasificada: 'Para revisar',
  aprobada: 'Aprobada',
  error: 'Error',
}

export const AREAS = ['Logística', 'Postventa', 'Administración', 'Ventas', 'Atención al cliente', 'Supervisión']

export function porcentaje(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return `${Math.round(valor * 100)}%`
}

export function fechaCorta(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Texto de cuánto falta (o cuánto pasó) para el vencimiento del SLA. */
export function textoSla(venceIso: string | null, ahora: Date = new Date()): string {
  if (!venceIso) return 'Sin SLA'
  const minutos = Math.round((new Date(venceIso).getTime() - ahora.getTime()) / 60000)
  const abs = Math.abs(minutos)
  const cantidad = abs >= 60 * 24 ? `${Math.floor(abs / 1440)} d` : abs >= 60 ? `${Math.floor(abs / 60)} h` : `${abs} min`
  return minutos < 0 ? `Vencido hace ${cantidad}` : `Vence en ${cantidad}`
}

export function usd(valor: number): string {
  return `US$ ${valor.toFixed(valor < 1 ? 4 : 2)}`
}
