import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Activity, LogOut, ShieldCheck } from "lucide-react";

export default function AdminShell({ children }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white grain">
      <div className="border-b border-white/5">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#CCFF00] flex items-center justify-center">
              <Activity className="w-5 h-5 text-black" strokeWidth={3} />
            </div>
            <div>
              <div className="font-head text-base font-extrabold leading-none">FUTSAL LOAD HUB</div>
              <div className="flex items-center gap-1.5 text-[10px] text-[#CCFF00] tracking-[0.3em] uppercase mt-0.5">
                <ShieldCheck className="w-3 h-3" /> Administração
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Sessão de</div>
              <div className="text-xs font-bold" data-testid="admin-email">{user?.email}</div>
            </div>
            <button
              onClick={async () => { await logout(); navigate("/login"); }}
              data-testid="admin-logout"
              className="flex items-center gap-1.5 text-[#A3A3A3] hover:text-white text-xs uppercase tracking-widest"
            >
              <LogOut className="w-3.5 h-3.5" /> Sair
            </button>
          </div>
        </div>
      </div>
      <main className="max-w-6xl mx-auto p-6">{children}</main>
    </div>
  );
}
