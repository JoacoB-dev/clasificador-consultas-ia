import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, token } from './api'
import type { Usuario } from './tipos'

interface EstadoAuth {
  usuario: Usuario | null
  cargando: boolean
  entrar: (email: string, password: string) => Promise<void>
  salir: () => void
}

const ContextoAuth = createContext<EstadoAuth | null>(null)

export function ProveedorAuth({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [cargando, setCargando] = useState(Boolean(token.leer()))

  // Si hay un token guardado, validamos que siga sirviendo
  useEffect(() => {
    if (!token.leer()) return
    api
      .get<Usuario>('/auth/yo')
      .then(setUsuario)
      .catch(() => token.borrar())
      .finally(() => setCargando(false))
  }, [])

  useEffect(() => {
    const alVencer = () => setUsuario(null)
    window.addEventListener('sesion-vencida', alVencer)
    return () => window.removeEventListener('sesion-vencida', alVencer)
  }, [])

  const entrar = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ access_token: string; usuario: Usuario }>('/auth/login', { email, password })
    token.guardar(r.access_token)
    setUsuario(r.usuario)
  }, [])

  const salir = useCallback(() => {
    token.borrar()
    setUsuario(null)
  }, [])

  return <ContextoAuth.Provider value={{ usuario, cargando, entrar, salir }}>{children}</ContextoAuth.Provider>
}

export function useAuth(): EstadoAuth {
  const ctx = useContext(ContextoAuth)
  if (!ctx) throw new Error('useAuth fuera de ProveedorAuth')
  return ctx
}
