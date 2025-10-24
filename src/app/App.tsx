import {
	BrowserRouter as Router,
	Routes,
	Route,
	useLocation,
} from 'react-router-dom'
import { Navbar } from "@/components/widgets/navbar";
import  AuthPage  from "../components/pages/AuthPage";
import SettingsPage from "../components/pages/SettingsPage";
import DashboardPage from "../components/pages/DashboardPage";
import HistoryPage from "../components/pages/HistoryPage";
import ListPage from "../components/pages/ListPage";
import { Toaster } from '@/components/ui/sonner'

function AppLayout() {
  const location = useLocation()
  const isHideNavbar = location.pathname === "/auth"
  return (
		<div className='min-h-screen flex flex-row bg-gray-50 text-gray-900 font-rostelecom'>
			{!isHideNavbar && <Navbar />}
			<main className='flex-1'>
				<Routes>
					<Route path='/' element={<DashboardPage />} />
					<Route path='/auth' element={<AuthPage />} />
					<Route path='/settings' element={<SettingsPage />} />
					<Route path='/history' element={<HistoryPage />} />
					<Route path='/list' element={<ListPage />} />
				</Routes>
			</main>
			<Toaster richColors position='bottom-right' />
		</div>
	)
}

export default function App(){
  return(
    <Router>
      <AppLayout/>
    </Router>
  )
}