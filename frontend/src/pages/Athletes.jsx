import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import PlayerAvatar from "@/components/PlayerAvatar";

export default function Athletes() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", position: "", jersey_number: "" });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/athletes");
      setList(data);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await http.post("/athletes", {
        name: form.name,
        position: form.position || null,
        jersey_number: form.jersey_number ? Number(form.jersey_number) : null,
      });
      toast.success("Atleta criado");
      setForm({ name: "", position: "", jersey_number: "" });
      setOpen(false);
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function remove(id) {
    if (!window.confirm("Eliminar atleta e respetivas sessões?")) return;
    try {
      await http.delete(`/athletes/${id}`);
      toast.success("Atleta eliminado");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Plantel</div>
          <h1 className="font-head text-5xl md:text-6xl font-black leading-none">ATLETAS</h1>
        </div>
        <button className="fld-btn-primary flex items-center gap-2" onClick={() => setOpen(!open)} data-testid="add-athlete-btn">
          <Plus className="w-4 h-4" /> {open ? "FECHAR" : "ADICIONAR"}
        </button>
      </div>

      {open && (
        <form onSubmit={create} className="fld-card max-w-2xl space-y-4" data-testid="athlete-form">
          <div className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="fld-label">Nome</label>
              <input className="fld-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="athlete-name" />
            </div>
            <div>
              <label className="fld-label">Nº</label>
              <input className="fld-input" type="number" min="1" max="99" value={form.jersey_number} onChange={(e) => setForm({ ...form, jersey_number: e.target.value })} data-testid="athlete-number" />
            </div>
          </div>
          <div>
            <label className="fld-label">Posição</label>
            <select className="fld-input" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} data-testid="athlete-position">
              <option value="">— Selecionar —</option>
              <option value="Guarda-Redes">Guarda-Redes</option>
              <option value="Fixo">Fixo</option>
              <option value="Ala">Ala</option>
              <option value="Pivô">Pivô</option>
              <option value="Universal">Universal</option>
            </select>
          </div>
          <button type="submit" className="fld-btn-primary" disabled={saving} data-testid="athlete-save">
            {saving ? "A GUARDAR..." : "CRIAR ATLETA"}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-[#A3A3A3]">A carregar...</div>
      ) : list.length === 0 ? (
        <div className="fld-card text-center py-16" data-testid="no-athletes">
          <div className="font-head text-2xl">SEM ATLETAS</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Adicione o primeiro atleta para começar.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((a) => (
            <div key={a.id} className="fld-card fld-card-hover relative" data-testid={`athlete-card-${a.id}`}>
              <div className="flex items-start justify-between mb-3">
                <PlayerAvatar athlete={a} size={56} editable onChange={load} />
                <div className="flex items-center gap-3">
                  <div className="metric-num text-[#CCFF00] text-3xl">{a.jersey_number ? `#${a.jersey_number}` : "—"}</div>
                  <button onClick={() => remove(a.id)} className="text-[#525252] hover:text-[#FF3B30]" data-testid={`delete-athlete-${a.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <Link to={`/atletas/${a.id}`} className="block">
                <div className="font-head text-xl font-bold mb-1 hover:text-[#CCFF00] transition-colors">{a.name}</div>
                <div className="text-xs text-[#A3A3A3] uppercase tracking-widest">{a.position || "Sem posição"}</div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
