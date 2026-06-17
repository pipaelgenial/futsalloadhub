import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Activity, LogOut, ClipboardEdit, History, User } from "lucide-react";

const PLAYER_ITEMS = [
  { to: "/atleta", label: "RESUMO", icon: User, end: true },
  { to: "/atleta/registar", label: "REGISTAR", icon: ClipboardEdit },
  { to: "/atleta/historico", label: "HISTÓRICO", icon: History },
];

export default function PlayerShell({ children }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);

  useEffect(() => {
    http.get("/player/me").then(({ data }) => setMe(data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white grain">
      <div className="border-b border-white/5">
        <div className="max-w-4xl mx-auto flex items-center justify-between px-5 py-4 gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 bg-[#CCFF00] flex items-center justify-center shrink-0">
              <Activity className="w-5 h-5 text-black" strokeWidth={3} />
            </div>
            <div className="min-w-0">
              <div className="font-head text-sm font-extrabold leading-none truncate">{me?.athlete?.name || user?.name}</div>
              <div className="text-[10px] text-[#CCFF00] tracking-[0.3em] uppercase mt-0.5 truncate">
                {me?.team?.name || "Vista de Atleta"}
              </div>
            </div>
          </div>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            data-testid="player-logout"
            className="flex items-center gap-1.5 text-[#A3A3A3] hover:text-white text-xs uppercase tracking-widest shrink-0"
          >
            <LogOut className="w-3.5 h-3.5" /> Sair
          </button>
        </div>
        <div className="max-w-4xl mx-auto flex items-center gap-1 px-5 pb-0">
          {PLAYER_ITEMS.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              data-testid={`player-nav-${it.label.toLowerCase()}`}
              className={({ isActive }) => `flex items-center gap-1.5 px-3 py-2.5 text-[11px] uppercase tracking-widest border-b-2 transition-all ${isActive ? "border-[#CCFF00] text-[#CCFF00]" : "border-transparent text-[#A3A3A3] hover:text-white"}`}
            >
              <it.icon className="w-3.5 h-3.5" /> {it.label}
            </NavLink>
          ))}
        </div>
      </div>
      <main className="max-w-4xl mx-auto p-5 sm:p-6">{children}</main>
    </div>
  );
}
