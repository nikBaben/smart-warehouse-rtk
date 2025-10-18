import  AuthPage  from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";

function App() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50 text-gray-900 font-rostelecom">
      <main className="flex-1">
        <DashboardPage />
      </main>
    </div>
  );
}


export default App;
