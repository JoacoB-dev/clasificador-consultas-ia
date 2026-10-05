import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Layout({ children }: { children: ReactNode }) {
  const { usuario, salir } = useAuth()
  return (
    <div className="app">
      <header className="barra">
        <div className="marca">
          <span className="logo" aria-hidden>≡</span>
          <div>
            <strong>Mesa de ayuda</strong>
            <small>Bazar La Esquina · demo</small>
          </div>
        </div>
        <nav>
          <NavLink to="/" end>Bandeja</NavLink>
          <NavLink to="/importar">Importar</NavLink>
          {usuario?.rol === 'supervisor' && <NavLink to="/metricas">Métricas</NavLink>}
          <a href="/contacto" target="_blank" rel="noreferrer">Formulario público ↗</a>
        </nav>
        <div className="usuario">
          <span>
            {usuario?.nombre} <em className={`rol rol-${usuario?.rol}`}>{usuario?.rol}</em>
          </span>
          <button className="boton-link" onClick={salir}>Salir</button>
        </div>
      </header>
      <main className="contenido">{children}</main>
    </div>
  )
}
