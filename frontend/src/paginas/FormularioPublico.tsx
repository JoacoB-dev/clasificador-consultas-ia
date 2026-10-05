import { useState, type FormEvent } from 'react'
import { api } from '../api'

// Formulario de contacto "público" de la tienda ficticia: no requiere login
export default function FormularioPublico() {
  const [datos, setDatos] = useState({ nombre: '', email: '', asunto: '', mensaje: '' })
  const [enviada, setEnviada] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const cambiar = (campo: keyof typeof datos) => (e: { target: { value: string } }) =>
    setDatos({ ...datos, [campo]: e.target.value })

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const r = await api.post<{ id: number }>('/consultas/formulario', { ...datos, nombre: datos.nombre || null })
      setEnviada(r.id)
      setDatos({ nombre: '', email: '', asunto: '', mensaje: '' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo enviar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pantalla-login">
      <form className="tarjeta login ancho" onSubmit={enviar}>
        <h1>Bazar La Esquina</h1>
        <p className="sutil">Contacto · tienda ficticia para la demo</p>
        {enviada && (
          <p className="exito">¡Gracias! Recibimos tu consulta (#{enviada}). Te vamos a responder por mail.</p>
        )}
        <label>
          Nombre
          <input value={datos.nombre} onChange={cambiar('nombre')} maxLength={150} />
        </label>
        <label>
          Email *
          <input type="email" value={datos.email} onChange={cambiar('email')} required />
        </label>
        <label>
          Asunto *
          <input value={datos.asunto} onChange={cambiar('asunto')} required minLength={3} maxLength={300} />
        </label>
        <label>
          Mensaje *
          <textarea rows={6} value={datos.mensaje} onChange={cambiar('mensaje')} required minLength={10} />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="boton primario" disabled={enviando}>
          {enviando ? 'Enviando…' : 'Enviar consulta'}
        </button>
      </form>
    </div>
  )
}
