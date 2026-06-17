import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, X, ShieldAlert } from "lucide-react";

const SEVERITY_META = {
  low: { label: "Ligeira", color: "#FFEA00" },
  medium: { label: "Moderada", color: "#FF9500" },
  high: { label: "Grave", color: "#FF3B30" },
};

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function InjuriesPanel({ athleteId, refreshKey, onChange }) {
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    type: "",
    body_part: "",
    start_date: todayISO(),
    end_date: "",
    severity: "medium",
    notes: "",
  });
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const { data } = await http.get(`/injuries?athlete_id=${athleteId}`);
      setList(data);
    } catch (err) { toast.error(formatApiError(err)); }
  }

  useEffect(() => { load(); }, [athleteId, refreshKey]);

  async function create(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await http.post("/injuries", {
        athlete_id: athleteId,
        type: form.type,
        body_part: form.body_part,
        start_date: form.start_date,
        end_date: form.end_date || null,
        severity: form.severity,
        notes: form.notes || null,
      });
      toast.success("Lesão registada");
      setForm({ type: "", body_part: "", start_date: todayISO(), end_date: "", severity: "medium", notes: "" });
      setOpen(false);
      load();
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function remove(id) {
    if (!window.confirm("Eliminar registo de lesão?")) return;
    try {
      await http.delete(`/injuries/${id}`);
      toast.success("Eliminada");
      load();
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  return (
    <div className="fld-card" data-testid="injuries-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-[#FF3B30]" />
          <div className="font-head text-2xl font-bold">HISTÓRICO DE LESÕES</div>
          <span className="metric-num text-[#525252] text-sm ml-2">{list.length}</span>
        </div>
        <button onClick={() => setOpen(!open)} className="fld-btn-ghost flex items-center gap-2 text-xs" data-testid="add-injury-btn">
          {open ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          {open ? "FECHAR" : "ADICIONAR"}
        </button>
      </div>

      {open && (
        <form onSubmit={create} className="space-y-4 border border-white/5 p-4 mb-5" data-testid="injury-form">
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="fld-label">Tipo</label>
              <input className="fld-input" placeholder="Ex: Entorse, Lesão muscular" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} required data-testid="injury-type" />
            </div>
            <div>
              <label className="fld-label">Zona Corporal</label>
              <input className="fld-input" placeholder="Ex: Tornozelo direito" value={form.body_part} onChange={(e) => setForm({ ...form, body_part: e.target.value })} required data-testid="injury-body" />
            </div>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <label className="fld-label">Início</label>
              <input className="fld-input" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} required data-testid="injury-start" />
            </div>
            <div>
              <label className="fld-label">Fim (opcional)</label>
              <input className="fld-input" type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} data-testid="injury-end" />
            </div>
            <div>
              <label className="fld-label">Severidade</label>
              <select className="fld-input" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} data-testid="injury-severity">
                <option value="low">Ligeira</option>
                <option value="medium">Moderada</option>
                <option value="high">Grave</option>
              </select>
            </div>
          </div>
          <div>
            <label className="fld-label">Notas (opcional)</label>
            <textarea className="fld-input" rows="2" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="injury-notes" />
          </div>
          <button type="submit" disabled={saving} className="fld-btn-primary" data-testid="injury-save">
            {saving ? "A GUARDAR..." : "REGISTAR LESÃO"}
          </button>
        </form>
      )}

      {list.length === 0 ? (
        <div className="text-sm text-[#A3A3A3] py-6 text-center">Nenhuma lesão registada.</div>
      ) : (
        <div className="space-y-2">
          {list.map((inj) => {
            const sev = SEVERITY_META[inj.severity] || SEVERITY_META.medium;
            const active = !inj.end_date;
            return (
              <div key={inj.id} className="flex items-start gap-4 border border-white/5 p-3" data-testid={`injury-${inj.id}`}>
                <div className="w-1 self-stretch" style={{ background: sev.color }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="font-semibold">{inj.type}</div>
                    <span className="text-xs px-2 py-0.5 uppercase tracking-widest" style={{ color: sev.color, background: `${sev.color}1A`, border: `1px solid ${sev.color}40` }}>
                      {sev.label}
                    </span>
                    {active && (
                      <span className="text-xs px-2 py-0.5 uppercase tracking-widest text-[#FF3B30] border border-[#FF3B30]/40 bg-[#FF3B30]/10">
                        Ativa
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[#A3A3A3] mt-1">
                    {inj.body_part} · {inj.start_date}{inj.end_date ? ` → ${inj.end_date}` : " → em curso"}
                  </div>
                  {inj.notes && <div className="text-xs text-[#525252] mt-1">{inj.notes}</div>}
                </div>
                <button onClick={() => remove(inj.id)} className="text-[#525252] hover:text-[#FF3B30]" data-testid={`delete-injury-${inj.id}`}>
                  <X className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
