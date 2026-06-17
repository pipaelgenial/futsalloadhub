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
import AdminPanel from "@/pages/AdminPanel";
import AdminShell from "@/components/AdminShell";
import PlayerShell from "@/components/PlayerShell";
import PlayerHome from "@/pages/PlayerHome";
import PlayerLogSession from "@/pages/PlayerLogSession";
import PlayerSessions from "@/pages/PlayerSessions";
import InviteAccept from "@/pages/InviteAccept";
import "@/index.css";

function Loading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
      <div className="font-head text-[#CCFF00] tracking-widest">A CARREGAR...</div>
    </div>
  );
}

function ProtectedCoach({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  if (user.role === "player") return <Navigate to="/atleta" replace />;
  return <AppShell>{children}</AppShell>;
}

function ProtectedAdmin({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <AdminShell>{children}</AdminShell>;
}

function ProtectedPlayer({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "player") return <Navigate to="/" replace />;
  return <PlayerShell>{children}</PlayerShell>;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) {
    if (user.role === "admin") return <Navigate to="/admin" replace />;
    if (user.role === "player") return <Navigate to="/atleta" replace />;
    return <Navigate to="/" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster theme="dark" position="top-right" />
        <Routes>
          {/* Public */}
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
          <Route path="/convite/:token" element={<InviteAccept />} />

          {/* Admin */}
          <Route path="/admin" element={<ProtectedAdmin><AdminPanel /></ProtectedAdmin>} />

          {/* Coach */}
          <Route path="/" element={<ProtectedCoach><Dashboard /></ProtectedCoach>} />
          <Route path="/equipa" element={<ProtectedCoach><TeamProfile /></ProtectedCoach>} />
          <Route path="/atletas" element={<ProtectedCoach><Athletes /></ProtectedCoach>} />
          <Route path="/atletas/:id" element={<ProtectedCoach><AthleteDetail /></ProtectedCoach>} />
          <Route path="/registar-sessao" element={<ProtectedCoach><LogSession /></ProtectedCoach>} />
          <Route path="/resumo-semanal" element={<ProtectedCoach><WeeklySummary /></ProtectedCoach>} />
          <Route path="/resumo-mensal" element={<ProtectedCoach><MonthlySummary /></ProtectedCoach>} />
          <Route path="/comparar" element={<ProtectedCoach><Compare /></ProtectedCoach>} />
          <Route path="/calendario" element={<ProtectedCoach><CalendarPage /></ProtectedCoach>} />

          {/* Player */}
          <Route path="/atleta" element={<ProtectedPlayer><PlayerHome /></ProtectedPlayer>} />
          <Route path="/atleta/registar" element={<ProtectedPlayer><PlayerLogSession /></ProtectedPlayer>} />
          <Route path="/atleta/historico" element={<ProtectedPlayer><PlayerSessions /></ProtectedPlayer>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
