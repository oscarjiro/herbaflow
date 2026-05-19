import { Outlet } from 'react-router-dom'
import NavBar from '@/components/layout/NavBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-hf-bg">
      <NavBar />
      <Outlet />
    </div>
  )
}
