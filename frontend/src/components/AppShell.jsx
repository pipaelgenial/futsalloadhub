import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { LayoutDashboard, Users, ClipboardEdit, Building2, LogOut, Activity, CalendarRange, GitCompareArrows, CalendarDays } from "lucide-react";
import TeamSwitcher from "@/components/TeamSwitcher";
import NotificationsBell from "@/components/NotificationsBell";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/equipa", label: "Equipa", icon: Building2, testid: "nav-team" },
  { to: "/atletas", label: "Atletas", icon: Users, testid: "nav-athletes" },
  { to: "/registar-sessao", label: "Registar Sessão", icon: ClipboardEdit, testid: "nav-log" },
  { to: "/calendario", label: "Calendário", icon: CalendarDays, testid: "nav-calendar" },
  { to: "/resumo-semanal", label: "Resumo Semanal", icon: CalendarRange, testid: "nav-weekly" },
  { to: "/comparar", label: "Comparar", icon: GitCompareArrows, testid: "nav-compare" },
];

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex grain">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 bg-[#0A0A0A] hidden md:flex flex-col p-6 sticky top-0 h-screen z-10">
        <button
          type="button"
          onClick={() => navigate("/")}
          data-testid="brand-home"
          aria-label="Ir para o Dashboard"
          className="flex items-center gap-2 mb-6 text-left hover:opacity-80 transition-opacity"
        >
          <div className="w-10 h-10 bg-[#CCFF00] flex items-center justify-center">
            <Activity className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div>
            <div className="font-head text-xl font-extrabold leading-none">FUTSAL</div>
            <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-0.5">LOAD HUB</div>
          </div>
        </button>

        {/* Team switcher + notifications */}
        <div className="mb-6 flex items-stretch gap-2">
          <div className="flex-1 min-w-0">
            <TeamSwitcher />
          </div>
          <NotificationsBell align="left" />
        </div>

        <nav className="flex-1 flex flex-col gap-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              data-testid={l.testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-3 font-head tracking-wider text-sm transition-all border-l-2 ${
                  isActive
                    ? "border-[#CCFF00] bg-white/5 text-white"
                    : "border-transparent text-[#A3A3A3] hover:text-white hover:bg-white/5"
                }`
              }
            >
              <l.icon className="w-4 h-4" />
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/5 pt-4 mt-4">
          <div className="text-xs text-[#525252] uppercase tracking-widest mb-1">Treinador</div>
          <div className="text-sm font-medium truncate" data-testid="user-name">{user?.name}</div>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            data-testid="logout-btn"
            className="mt-3 flex items-center gap-2 text-xs text-[#A3A3A3] hover:text-[#FF3B30] transition-colors uppercase tracking-widest"
          >
            <LogOut className="w-3.5 h-3.5" /> Sair
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 relative z-[2]">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between p-4 border-b border-white/5 gap-3">
          <button
            type="button"
            onClick={() => navigate("/")}
            data-testid="brand-home-mobile"
            aria-label="Ir para o Dashboard"
            className="flex items-center gap-2 shrink-0 hover:opacity-80 transition-opacity"
          >
            <div className="w-8 h-8 bg-[#CCFF00] flex items-center justify-center">
              <Activity className="w-5 h-5 text-black" strokeWidth={3} />
            </div>
            <span className="font-head font-extrabold text-sm">FUTSAL</span>
          </button>
          <div className="flex-1 min-w-0 max-w-[260px]">
            <TeamSwitcher />
          </div>
          <NotificationsBell testid="notifications-bell-mobile" />
          <button onClick={async () => { await logout(); navigate("/login"); }} className="text-[#A3A3A3] shrink-0" data-testid="logout-btn-mobile">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
        <div className="md:hidden flex overflow-x-auto border-b border-white/5">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-3 font-head text-xs whitespace-nowrap border-b-2 ${
                  isActive ? "border-[#CCFF00] text-white" : "border-transparent text-[#A3A3A3]"
                }`
              }
            >
              <l.icon className="w-3.5 h-3.5" /> {l.label}
            </NavLink>
          ))}
        </div>

        <div className="p-4 md:p-8 max-w-[1600px]">{children}</div>
      </main>
    </div>
  );
}
