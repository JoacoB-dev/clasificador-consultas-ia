// Cliente HTTP mínimo: agrega el token y convierte errores de la API en mensajes legibles
const CLAVE_TOKEN = 'consultas.token'

export class ErrorApi extends Error {
  status: number
  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.status = status
  }
}

export const token = {
  leer: () => localStorage.getItem(CLAVE_TOKEN),
  guardar: (valor: string) => localStorage.setItem(CLAVE_TOKEN, valor),
  borrar: () => localStorage.removeItem(CLAVE_TOKEN),
}

function mensajeDeError(cuerpo: unknown, status: number): string {
  const detalle = (cuerpo as { detail?: unknown } | null)?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle)) {
    // Errores de validación de FastAPI: [{loc, msg}]
    return detalle.map((e: { loc?: string[]; msg?: string }) => `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
  }
  return `Error ${status}`
}

export async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const headers = new Headers(opciones.headers)
  const t = token.leer()
  if (t) headers.set('Authorization', `Bearer ${t}`)
  if (opciones.body && !(opciones.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const respuesta = await fetch(`/api${ruta}`, { ...opciones, headers })
  const texto = await respuesta.text()
  const cuerpo = texto ? JSON.parse(texto) : null
  if (!respuesta.ok) {
    if (respuesta.status === 401 && t) {
      token.borrar()
      window.dispatchEvent(new Event('sesion-vencida'))
    }
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status))
  }
  return cuerpo as T
}

export const api = {
  get: <T,>(ruta: string) => pedir<T>(ruta),
  post: <T,>(ruta: string, datos?: unknown) =>
    pedir<T>(ruta, { method: 'POST', body: datos instanceof FormData ? datos : JSON.stringify(datos ?? {}) }),
  patch: <T,>(ruta: string, datos: unknown) => pedir<T>(ruta, { method: 'PATCH', body: JSON.stringify(datos) }),
}
