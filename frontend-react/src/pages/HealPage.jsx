import Navbar from '../components/Navbar'
import HealDashboard from '../components/HealDashboard'

export default function HealPage() {
  return (
    <div className="page-shell heal-page">
      <Navbar variant="solid" />
      <HealDashboard />
    </div>
  )
}
