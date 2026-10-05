// Tipos que reflejan los esquemas de la API (app/esquemas.py)

export type Rol = 'operador' | 'supervisor'
export type Categoria =
  | 'envio'
  | 'producto_defectuoso'
  | 'devolucion'
  | 'facturacion'
  | 'consulta_producto'
  | 'cuenta'
  | 'otro'
export type Urgencia = 'baja' | 'media' | 'alta' | 'critica'
export type Estado = 'pendiente' | 'en_proceso' | 'clasificada' | 'aprobada' | 'error'

export interface Usuario {
  id: number
  email: string
  nombre: string
  rol: Rol
}

export interface ConsultaResumen {
  id: number
  canal: string
  remitente_nombre: string | null
  remitente_email: string
  asunto: string
  recibida_en: string
  estado: Estado
  categoria: Categoria | null
  urgencia: Urgencia | null
  sentimiento: string | null
  resumen: string | null
  area_asignada: string | null
  sla_vence_en: string | null
  sla_vencido: boolean
  corregida: boolean
}

export interface Correccion {
  id: number
  campo: string
  valor_anterior: string | null
  valor_nuevo: string
  usuario_id: number
  creada_en: string
}

export interface ConsultaDetalle extends ConsultaResumen {
  cuerpo: string
  datos_extraidos: Record<string, string | number | null> | null
  borrador_respuesta: string | null
  respuesta_final: string | null
  confianza: number | null
  categoria_modelo: Categoria | null
  urgencia_modelo: Urgencia | null
  clasificador: string | null
  reglas_aplicadas: string[] | null
  intentos: number
  error_detalle: string | null
  clasificada_en: string | null
  revisada_en: string | null
  aprobada_en: string | null
  correcciones: Correccion[]
}

export interface Pagina<T> {
  items: T[]
  total: number
  pagina: number
  tamanio: number
}

export interface PrecisionCategoria {
  categoria: Categoria
  predichas: number
  correctas: number
  reales: number
  precision: number | null
  recall: number | null
}

export interface MetricasPrecision {
  total_revisadas: number
  correctas: number
  exactitud: number | null
  por_categoria: PrecisionCategoria[]
  matriz_confusion: { modelo: Categoria; real: Categoria; cantidad: number }[]
}

export interface MetricasUso {
  llamadas: number
  tokens_entrada: number
  tokens_salida: number
  costo_total_usd: number
  costo_promedio_usd: number | null
  por_modelo: {
    modelo: string
    llamadas: number
    fallidas: number
    tokens_entrada: number
    tokens_salida: number
    costo_usd: number
    duracion_promedio_ms: number
  }[]
}

export interface ResumenBandeja {
  por_estado: Record<string, number>
  por_area: Record<string, number>
  sla_vencidas: number
  clasificador_activo: string
}

export interface ResultadoImportacion {
  creadas: { id: number; estado: Estado; encolada: boolean }[]
  duplicadas: number
  errores: string[]
}
