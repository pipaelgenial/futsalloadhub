import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "sonner";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import TeamProfile from "@/pages/TeamProfile";
import Athletes from "@/pages/Athletes";
import LogSession from "@/pages/LogSession";
import AthleteDetail from "@/pages/AthleteDetail";
import MonthlySummary from "@/pages/MonthlySummary";
import WeeklySummary from "@/pages/WeeklySummary";
import Compare from "@/pages/Compare";
import CalendarPage from "@/pages/Calendar";
import AppShell from "@/components/AppShell";
import "@/index.css";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="font-head text-[#CCFF00] tracking-widest">A CARREGAR...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster theme="dark" position="top-right" />
        <Routes>
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
          <Route path="/" element={<Protected><Dashboard /></Protected>} />
          <Route path="/equipa" element={<Protected><TeamProfile /></Protected>} />
          <Route path="/atletas" element={<Protected><Athletes /></Protected>} />
          <Route path="/atletas/:id" element={<Protected><AthleteDetail /></Protected>} />
          <Route path="/registar-sessao" element={<Protected><LogSession /></Protected>} />
          <Route path="/resumo-semanal" element={<Protected><WeeklySummary /></Protected>} />
          <Route path="/resumo-mensal" element={<Protected><MonthlySummary /></Protected>} />
          <Route path="/comparar" element={<Protected><Compare /></Protected>} />
          <Route path="/calendario" element={<Protected><CalendarPage /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
