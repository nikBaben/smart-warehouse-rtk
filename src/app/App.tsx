import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { Navbar } from "@/components/widgets/navbar";
import  AuthPage  from "../components/pages/AuthPage";
import SettingsPage from "../components/pages/SettingsPage";
import DashboardPage from "../components/pages/DashboardPage";
import HistoryPage from "../components/pages/HistoryPage";
import ListPage from "../components/pages/ListPage";

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-row bg-gray-50 text-gray-900 font-rostelecom">
        <Navbar /> {/* Наш боковой navbar */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/history" element={<HistoryPage/>} />
            <Route path="/list" element={<ListPage/>} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;