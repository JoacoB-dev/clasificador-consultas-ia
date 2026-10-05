import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Login() {
  const { usuario, entrar } = useAuth()
  const [email, setEmail] = useState('supervisor@demo.local')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await entrar(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo ingresar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pantalla-login">
      <form className="tarjeta login" onSubmit={enviar}>
        <h1>Mesa de ayuda</h1>
        <p className="sutil">Clasificador de consultas con IA · proyecto de portfolio</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="boton primario" disabled={enviando}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>
        <p className="ayuda">
          Usuarios demo: <code>supervisor@demo.local</code> / <code>operador@demo.local</code> — contraseña{' '}
          <code>demo1234</code>
        </p>
      </form>
    </div>
  )
}
