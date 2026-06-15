import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Activity } from "lucide-react";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form.email, form.password, form.name);
      toast.success("Conta criada");
      navigate("/");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setLoading(false); }
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
      <form onSubmit={onSubmit} className="w-full max-w-sm relative z-[2]" data-testid="register-form">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-10 h-10 bg-[#CCFF00] flex items-center justify-center">
            <Activity className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div>
            <div className="font-head text-xl font-extrabold leading-none">FUTSAL</div>
            <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-0.5">LOAD HUB</div>
          </div>
        </div>

        <h2 className="font-head text-4xl font-black mb-8">CRIAR CONTA</h2>

        <label className="fld-label">Nome</label>
        <input className="fld-input mb-5" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="reg-name" required />

        <label className="fld-label">Email</label>
        <input className="fld-input mb-5" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="reg-email" required />

        <label className="fld-label">Password (min. 6)</label>
        <input className="fld-input mb-7" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="reg-password" required minLength={6} />

        <button type="submit" disabled={loading} className="fld-btn-primary w-full" data-testid="reg-submit">
          {loading ? "A CRIAR..." : "CRIAR CONTA"}
        </button>

        <div className="mt-6 text-sm text-[#A3A3A3]">
          Já tem conta?{" "}
          <Link to="/login" className="text-[#CCFF00] hover:underline" data-testid="goto-login">Entrar</Link>
        </div>
      </form>
    </div>
  );
}
