import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './componentes/Layout'
import Bandeja from './paginas/Bandeja'
import Detalle from './paginas/Detalle'
import FormularioPublico from './paginas/FormularioPublico'
import Importar from './paginas/Importar'
import Login from './paginas/Login'
import Metricas from './paginas/Metricas'

function Protegida({ children, soloSupervisor = false }: { children: React.ReactNode; soloSupervisor?: boolean }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <p className="centrado">Cargando…</p>
  if (!usuario) return <Navigate to="/login" replace />
  if (soloSupervisor && usuario.rol !== 'supervisor') return <Navigate to="/" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/contacto" element={<FormularioPublico />} />
      <Route path="/" element={<Protegida><Bandeja /></Protegida>} />
      <Route path="/consultas/:id" element={<Protegida><Detalle /></Protegida>} />
      <Route path="/importar" element={<Protegida><Importar /></Protegida>} />
      <Route path="/metricas" element={<Protegida soloSupervisor><Metricas /></Protegida>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
