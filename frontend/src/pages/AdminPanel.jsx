import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Check, RotateCcw, Trash2, ShieldCheck, ShieldAlert, Users, Search, KeyRound, Copy } from "lucide-react";

const STATUS_META = {
  pending: { label: "Pendente", color: "#FF9500", bg: "rgba(255,149,0,0.10)" },
  active: { label: "Ativo", color: "#CCFF00", bg: "rgba(204,255,0,0.10)" },
  suspended: { label: "Suspenso", color: "#FF3B30", bg: "rgba(255,59,48,0.10)" },
};

const ROLE_META = {
  admin: { label: "Admin", color: "#CCFF00" },
  coach: { label: "Treinador", color: "#A3A3A3" },
  player: { label: "Atleta", color: "#FFEA00" },
};

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all"); // all | pending | active | suspended
  const [acting, setActing] = useState(null);
  const [tempPassword, setTempPassword] = useState(null); // { email, password }

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/admin/users");
      setUsers(data || []);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function callAction(userId, endpoint, successMsg, body) {
    setActing(userId);
    try {
      await http.post(`/admin/users/${userId}/${endpoint}`, body || {});
      toast.success(successMsg);
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setActing(null); }
  }

  async function removeUser(u) {
    if (!window.confirm(`Eliminar definitivamente "${u.email}" e TODOS os seus dados (equipas, atletas, sessões)?`)) return;
    setActing(u.id);
    try {
      await http.delete(`/admin/users/${u.id}`);
      toast.success("Utilizador eliminado");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setActing(null); }
  }

  async function resetPassword(u) {
    if (!window.confirm(`Gerar password temporária para "${u.email}"?\n\nO utilizador não conseguirá entrar com a password antiga e terá de usar a nova. Deve alterá-la após o próximo login.`)) return;
    setActing(u.id);
    try {
      const { data } = await http.post(`/admin/users/${u.id}/reset-password`);
      setTempPassword({ email: data.email, password: data.temp_password });
      toast.success("Password temporária gerada");
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setActing(null); }
  }

  async function copyTempPassword() {
    if (!tempPassword) return;
    try {
      await navigator.clipboard.writeText(tempPassword.password);
      toast.success("Password copiada");
    } catch {
      toast.error("Não foi possível copiar automaticamente");
    }
  }

  const filtered = users.filter((u) => {
    if (filter !== "all" && u.status !== filter) return false;
    if (query && !u.email.toLowerCase().includes(query.toLowerCase()) && !(u.name || "").toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  const counts = {
    all: users.length,
    pending: users.filter((u) => u.status === "pending").length,
    active: users.filter((u) => u.status === "active").length,
    suspended: users.filter((u) => u.status === "suspended").length,
  };

  return (
    <div className="space-y-6" data-testid="admin-panel">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Gestão de Utilizadores</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">CONTAS</h1>
          <p className="text-[#A3A3A3] text-xs sm:text-sm mt-2">Validar, suspender e eliminar contas. Cada utilizador é uma ilha de dados.</p>
        </div>
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-[#CCFF00]" />
          <span className="metric-num text-2xl">{users.length}</span>
          <span className="text-[#A3A3A3] text-xs uppercase tracking-widest">contas</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {["all", "pending", "active", "suspended"].map((f) => {
          const m = f === "all" ? { label: "Todos", color: "#A3A3A3" } : STATUS_META[f];
          const isActive = filter === f;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              data-testid={`filter-${f}`}
              className="text-[10px] uppercase tracking-widest px-3 py-1.5 border transition-all"
              style={{
                borderColor: isActive ? m.color : "rgba(255,255,255,0.10)",
                color: isActive ? m.color : "#A3A3A3",
                background: isActive ? `${m.color}10` : "transparent",
              }}
            >
              {m.label} ({counts[f]})
            </button>
          );
        })}
        <div className="flex-1" />
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#525252] absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Pesquisar..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            data-testid="admin-search"
            className="fld-input py-1.5 pl-8 text-xs min-w-[200px]"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-[#A3A3A3]">A carregar...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-[#525252] text-sm">Sem utilizadores para mostrar.</div>
      ) : (
        <div className="space-y-2">
          {filtered.map((u) => {
            const status = STATUS_META[u.status] || STATUS_META.pending;
            const role = ROLE_META[u.role] || ROLE_META.coach;
            const isAdmin = u.role === "admin";
            return (
              <div
                key={u.id}
                data-testid={`user-row-${u.id}`}
                className="fld-card flex flex-col md:flex-row md:items-center gap-3 md:gap-4"
                style={{ borderLeft: `3px solid ${status.color}` }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {isAdmin && <ShieldCheck className="w-4 h-4 text-[#CCFF00]" />}
                    <span className="font-head text-sm font-bold truncate" data-testid={`user-email-${u.id}`}>{u.email}</span>
                    <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5" style={{ color: role.color, background: `${role.color}15`, border: `1px solid ${role.color}40` }} data-testid={`user-role-${u.id}`}>
                      {role.label}
                    </span>
                    <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5" style={{ color: status.color, background: status.bg, border: `1px solid ${status.color}40` }} data-testid={`user-status-${u.id}`}>
                      {status.label}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#A3A3A3] mt-1 truncate">{u.name || "—"}</div>
                  <div className="text-[10px] text-[#525252] mt-1 flex flex-wrap gap-3">
                    <span>Equipas: <span className="metric-num text-white">{u.stats?.teams || 0}</span>{u.role === "coach" && <span className="text-[#525252]">/{u.max_teams ?? 5}</span>}</span>
                    <span>Atletas: <span className="metric-num text-white">{u.stats?.athletes || 0}</span></span>
                    <span>Sessões: <span className="metric-num text-white">{u.stats?.sessions || 0}</span></span>
                    {u.last_login_at && <span>Último login: <span className="text-[#A3A3A3]">{new Date(u.last_login_at).toLocaleDateString("pt-PT")}</span></span>}
                  </div>
                  {u.role === "coach" && (
                    <div className="mt-2 flex items-center gap-2 flex-wrap" data-testid={`max-teams-row-${u.id}`}>
                      <span className="text-[10px] uppercase tracking-widest text-[#525252]">Limite de equipas:</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((n) => {
                          const cur = u.max_teams ?? 5;
                          const isActive = cur === n;
                          const tooLow = n < (u.stats?.teams || 0);
                          return (
                            <button
                              key={n}
                              onClick={() => callAction(u.id, `max-teams`, `Limite definido para ${n}`, { max_teams: n })}
                              disabled={acting === u.id || isActive || tooLow}
                              data-testid={`max-teams-${u.id}-${n}`}
                              className="text-[10px] font-head px-2 py-1 border transition-all"
                              style={{
                                borderColor: isActive ? "#CCFF00" : tooLow ? "rgba(255,59,48,0.25)" : "rgba(255,255,255,0.10)",
                                color: isActive ? "#CCFF00" : tooLow ? "#FF3B30" : "#A3A3A3",
                                background: isActive ? "rgba(204,255,0,0.10)" : "transparent",
                                cursor: tooLow ? "not-allowed" : "pointer",
                              }}
                              title={tooLow ? "Coach já tem mais equipas do que este limite" : ""}
                            >
                              {n}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {!isAdmin && u.status === "pending" && (
                    <button
                      onClick={() => callAction(u.id, "validate", "Conta validada")}
                      disabled={acting === u.id}
                      data-testid={`validate-${u.id}`}
                      className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 border border-[#CCFF00]/40 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" /> Validar
                    </button>
                  )}
                  {!isAdmin && u.status === "active" && (
                    <button
                      onClick={() => callAction(u.id, "suspend", "Conta suspensa")}
                      disabled={acting === u.id}
                      data-testid={`suspend-${u.id}`}
                      className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 border border-[#FF9500]/40 text-[#FF9500] hover:bg-[#FF9500]/10 transition-all flex items-center gap-1"
                    >
                      <ShieldAlert className="w-3 h-3" /> Suspender
                    </button>
                  )}
                  {!isAdmin && u.status === "suspended" && (
                    <button
                      onClick={() => callAction(u.id, "reactivate", "Conta reativada")}
                      disabled={acting === u.id}
                      data-testid={`reactivate-${u.id}`}
                      className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 border border-[#CCFF00]/40 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all flex items-center gap-1"
                    >
                      <RotateCcw className="w-3 h-3" /> Reativar
                    </button>
                  )}
                  {!isAdmin && (
                    <button
                      onClick={() => resetPassword(u)}
                      disabled={acting === u.id}
                      data-testid={`reset-password-${u.id}`}
                      title="Gerar password temporária"
                      className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 border border-[#FFEA00]/40 text-[#FFEA00] hover:bg-[#FFEA00]/10 transition-all flex items-center gap-1"
                    >
                      <KeyRound className="w-3 h-3" /> Reset Pass
                    </button>
                  )}
                  {!isAdmin && (
                    <button
                      onClick={() => removeUser(u)}
                      disabled={acting === u.id}
                      data-testid={`delete-user-${u.id}`}
                      className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 border border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/10 transition-all flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> Eliminar
                    </button>
                  )}
                  {isAdmin && (
                    <span className="text-[10px] uppercase tracking-widest px-2.5 py-1.5 text-[#525252]">
                      Conta protegida
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Temp password modal */}
      {tempPassword && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" data-testid="temp-password-modal">
          <div className="bg-[#0F0F0F] border border-[#FFEA00]/40 max-w-md w-full p-6">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound className="w-5 h-5 text-[#FFEA00]" />
              <h2 className="font-head text-lg font-extrabold uppercase tracking-widest">Password Temporária</h2>
            </div>
            <p className="text-sm text-[#A3A3A3] mb-4">
              Gerada para <span className="text-white font-semibold">{tempPassword.email}</span>.
              Copie e partilhe de forma segura com o utilizador. Esta password não será mostrada novamente.
            </p>
            <div className="flex items-center gap-2 mb-5">
              <code className="flex-1 bg-black/60 border border-white/10 px-4 py-3 font-mono text-lg text-[#FFEA00] tracking-wider text-center break-all" data-testid="temp-password-value">
                {tempPassword.password}
              </code>
              <button
                onClick={copyTempPassword}
                data-testid="copy-temp-password"
                className="p-3 border border-[#CCFF00]/40 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all"
                title="Copiar"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
            <div className="text-xs text-[#FFEA00]/80 bg-[#FFEA00]/5 border border-[#FFEA00]/20 p-3 mb-5">
              ⚠️ Recomende ao utilizador alterar esta password após o próximo login.
            </div>
            <button
              onClick={() => setTempPassword(null)}
              data-testid="close-temp-password"
              className="w-full py-2.5 bg-white text-black font-head text-xs uppercase tracking-widest hover:bg-[#CCFF00] transition-colors"
            >
              Fechar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
