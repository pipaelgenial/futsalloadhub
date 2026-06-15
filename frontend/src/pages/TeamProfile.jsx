import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function TeamProfile() {
  const [team, setTeam] = useState(null);
  const [form, setForm] = useState({ name: "", escalao: "", epoca: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await http.get("/team");
        if (data) {
          setTeam(data);
          setForm({ name: data.name, escalao: data.escalao, epoca: data.epoca });
        }
      } catch (err) {
        toast.error(formatApiError(err));
      } finally { setLoading(false); }
    })();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await http.post("/team", form);
      setTeam(data);
      toast.success("Dados da equipa guardados");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setSaving(false); }
  }

  if (loading) return <div className="text-[#A3A3A3]">A carregar...</div>;

  return (
    <div className="space-y-8">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Perfil</div>
        <h1 className="font-head text-5xl md:text-6xl font-black leading-none">EQUIPA</h1>
      </div>

      {!team && (
        <div className="fld-card border-l-4 border-l-[#CCFF00]" data-testid="empty-team-msg">
          <div className="font-head text-2xl font-bold">INSIRA DADOS DA EQUIPA</div>
          <p className="text-[#A3A3A3] text-sm mt-2">
            Preencha o nome, escalão e época da sua equipa para começar.
          </p>
        </div>
      )}

      <form onSubmit={onSubmit} className="fld-card max-w-2xl space-y-5" data-testid="team-form">
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
        <button type="submit" className="fld-btn-primary" disabled={saving} data-testid="team-save">
          {saving ? "A GUARDAR..." : "GUARDAR"}
        </button>
      </form>
    </div>
  );
}
