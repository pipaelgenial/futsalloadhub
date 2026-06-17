import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Activity, ShieldCheck } from "lucide-react";

export default function InviteAccept() {
  const { token } = useParams();
  const { acceptInvite } = useAuth();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ email: "", password: "", confirm: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    http.get(`/invite/${token}`)
      .then(({ data }) => setInfo(data))
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, [token]);

  async function onSubmit(e) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("As passwords não coincidem");
      return;
    }
    if (form.password.length < 6) {
      toast.error("A password deve ter pelo menos 6 caracteres");
      return;
    }
    setSaving(true);
    try {
      await acceptInvite(token, form.email, form.password, info.athlete_name);
      toast.success("Conta de atleta criada");
      navigate("/atleta");
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="font-head text-[#CCFF00] tracking-widest">A VALIDAR CONVITE...</div>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
        <div className="w-full max-w-md text-center relative z-[2]" data-testid="invite-error">
          <div className="w-12 h-12 bg-[#FF3B30] flex items-center justify-center mx-auto mb-6">
            <ShieldCheck className="w-7 h-7 text-white" strokeWidth={3} />
          </div>
          <h2 className="font-head text-3xl font-black mb-4">CONVITE INVÁLIDO</h2>
          <p className="text-[#A3A3A3] text-sm mb-8">{error || "Este convite não existe ou já foi utilizado."}</p>
          <Link to="/login" className="fld-btn-primary inline-block">IR PARA LOGIN</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
      <form onSubmit={onSubmit} className="w-full max-w-sm relative z-[2]" data-testid="invite-form">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-10 h-10 bg-[#CCFF00] flex items-center justify-center">
            <Activity className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div>
            <div className="font-head text-xl font-extrabold leading-none">FUTSAL</div>
            <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-0.5">LOAD HUB</div>
          </div>
        </div>

        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Convite de Atleta</div>
        <h2 className="font-head text-3xl font-black mb-4">BEM-VINDO, <span className="text-[#CCFF00]">{info.athlete_name?.toUpperCase()}</span></h2>
        <p className="text-[#A3A3A3] text-sm mb-6">
          Foste convidado pela <span className="text-white font-bold">{info.team_name}</span>{info.team_escalao && <> ({info.team_escalao})</>}. Define o teu acesso para começares a registar as tuas sessões.
        </p>

        <label className="fld-label">Email</label>
        <input className="fld-input mb-5" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="invite-email" required />

        <label className="fld-label">Password (min. 6)</label>
        <input className="fld-input mb-5" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="invite-password" required minLength={6} />

        <label className="fld-label">Confirmar Password</label>
        <input className="fld-input mb-7" type="password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} data-testid="invite-confirm" required minLength={6} />

        <button type="submit" disabled={saving} className="fld-btn-primary w-full" data-testid="invite-submit">
          {saving ? "A CRIAR..." : "CRIAR CONTA E ENTRAR"}
        </button>

        <div className="mt-6 text-xs text-[#525252]">
          Ao criar a tua conta passas a poder registar sessões e ver o teu histórico. Não terás acesso a dados de outros atletas.
        </div>
      </form>
    </div>
  );
}
