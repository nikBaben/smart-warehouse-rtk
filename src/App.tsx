import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { Navbar } from "@/components/ui/navbar";
import  AuthPage  from "./pages/AuthPage";
import SettingsPage from "./pages/SettingsPage";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import ListPage from "./pages/ListPage";

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