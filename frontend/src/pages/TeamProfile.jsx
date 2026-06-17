import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Pencil } from "lucide-react";
import TeamLogo from "@/components/TeamLogo";

const MAX_TEAMS = 5;

export default function TeamProfile() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // id or "new"
  const [form, setForm] = useState({ name: "", escalao: "", epoca: "" });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/teams");
      setTeams(data);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function startNew() {
    if (teams.length >= MAX_TEAMS) {
      toast.error(`Limite de ${MAX_TEAMS} equipas atingido`);
      return;
    }
    setEditing("new");
    setForm({ name: "", escalao: "", epoca: "" });
  }

  function startEdit(t) {
    setEditing(t.id);
    setForm({ name: t.name, escalao: t.escalao, epoca: t.epoca });
  }

  function cancel() {
    setEditing(null);
    setForm({ name: "", escalao: "", epoca: "" });
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing === "new") {
        await http.post("/teams", form);
        toast.success("Equipa criada");
      } else {
        await http.put(`/teams/${editing}`, form);
        toast.success("Equipa atualizada");
      }
      cancel();
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function remove(t) {
    const txt = window.prompt(`Eliminar a equipa "${t.name}" e TODOS os seus dados (atletas, sessões, lesões)?\n\nEscreva ELIMINAR (em maiúsculas) para confirmar:`);
    if (txt !== "ELIMINAR") return;
    try {
      await http.delete(`/teams/${t.id}`);
      toast.success("Equipa eliminada");
      load();
      window.dispatchEvent(new Event("active-team-changed"));
    } catch (err) { toast.error(formatApiError(err)); }
  }

  if (loading) return <div className="text-[#A3A3A3]">A carregar...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Perfil</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">EQUIPAS</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Até {MAX_TEAMS} equipas com dados independentes</p>
        </div>
        <button
          onClick={startNew}
          disabled={teams.length >= MAX_TEAMS || editing !== null}
          className="fld-btn-primary flex items-center gap-2 disabled:opacity-50"
          data-testid="add-team-btn"
        >
          <Plus className="w-4 h-4" /> NOVA EQUIPA <span className="text-xs">({teams.length}/{MAX_TEAMS})</span>
        </button>
      </div>

      {teams.length === 0 && editing !== "new" && (
        <div className="fld-card border-l-4 border-l-[#CCFF00]" data-testid="empty-team-msg">
          <div className="font-head text-xl sm:text-2xl font-bold">INSIRA DADOS DA EQUIPA</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Crie a sua primeira equipa para começar.</p>
        </div>
      )}

      {editing && (
        <form onSubmit={save} className="fld-card max-w-2xl space-y-5" data-testid="team-form">
          <div className="font-head text-lg">{editing === "new" ? "NOVA EQUIPA" : "EDITAR EQUIPA"}</div>
          <div>
            <label className="fld-label">Nome da Equipa</label>
            <input className="fld-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="team-name" placeholder="Ex: Sporting Futsal" />
          </div>
          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="fld-label">Escalão</label>
              <input className="fld-input" value={form.escalao} onChange={(e) => setForm({ ...form, escalao: e.target.value })} required data-testid="team-escalao" placeholder="Ex: Sénior, Sub-19" />
            </div>
            <div>
              <label className="fld-label">Época</label>
              <input className="fld-input" value={form.epoca} onChange={(e) => setForm({ ...form, epoca: e.target.value })} required data-testid="team-epoca" placeholder="Ex: 2025/2026" />
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" className="fld-btn-primary" disabled={saving} data-testid="team-save">
              {saving ? "A GUARDAR..." : "GUARDAR"}
            </button>
            <button type="button" className="fld-btn-ghost" onClick={cancel} data-testid="team-cancel">CANCELAR</button>
          </div>
        </form>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map((t) => (
          <div
            key={t.id}
            className={`fld-card relative ${t.active ? "border-l-4 border-l-[#CCFF00]" : ""}`}
            data-testid={`team-card-${t.id}`}
          >
            <div className="flex items-start gap-3 mb-3">
              <TeamLogo team={t} size={56} editable onChange={load} />
              <div className="flex-1 min-w-0">
                <div className="font-head text-lg font-bold truncate">{t.name}</div>
                <div className="text-xs text-[#A3A3A3] uppercase tracking-widest">{t.escalao}</div>
                <div className="text-xs text-[#525252] mt-0.5">{t.epoca}</div>
              </div>
              {t.active && (
                <span className="text-[10px] uppercase tracking-widest text-[#CCFF00] border border-[#CCFF00]/40 bg-[#CCFF00]/10 px-2 py-0.5" data-testid={`team-active-${t.id}`}>
                  Ativa
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/5">
              <button onClick={() => startEdit(t)} className="fld-btn-ghost text-xs flex items-center gap-1 flex-1" data-testid={`edit-team-${t.id}`}>
                <Pencil className="w-3.5 h-3.5" /> EDITAR
              </button>
              <button onClick={() => remove(t)} className="fld-btn-ghost text-xs flex items-center gap-1 text-[#FF3B30] border-[#FF3B30]/30 hover:bg-[#FF3B30]/10" data-testid={`delete-team-${t.id}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
