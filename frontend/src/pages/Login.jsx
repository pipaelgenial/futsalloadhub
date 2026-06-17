import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Activity } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success("Sessão iniciada");
      if (u.role === "admin") navigate("/admin");
      else if (u.role === "player") navigate("/atleta");
      else navigate("/");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setLoading(false); }
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] grid md:grid-cols-2 grain">
      {/* Visual side */}
      <div className="hidden md:block relative overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: "url(https://images.unsplash.com/photo-1630420598913-44208d36f9af?crop=entropy&cs=srgb&fm=jpg&q=85)",
            filter: "grayscale(0.3) contrast(1.1)",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-[#0A0A0A] via-[#0A0A0A]/80 to-transparent" />
        <div className="relative h-full flex flex-col justify-between p-12 z-10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-[#CCFF00] flex items-center justify-center">
              <Activity className="w-7 h-7 text-black" strokeWidth={3} />
            </div>
            <div>
              <div className="font-head text-2xl font-extrabold leading-none">FUTSAL</div>
              <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-1">LOAD HUB</div>
            </div>
          </div>
          <div className="max-w-md">
            <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-3">Monitoriza · Calcula · Previne</div>
            <h1 className="font-head text-5xl lg:text-6xl font-black leading-[0.9] mb-4">
              GERE A CARGA. <br />
              <span className="text-[#CCFF00]">PROTEGE</span> O ATLETA.
            </h1>
            <p className="text-[#A3A3A3] text-sm">
              ACWR, monotonia, strain e alertas de lesão em tempo real para a tua equipa de futsal.
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-8 md:p-16 relative z-[2]">
        <form onSubmit={onSubmit} className="w-full max-w-sm" data-testid="login-form">
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Acesso Treinador</div>
          <h2 className="font-head text-4xl font-black mb-8">INICIAR SESSÃO</h2>

          <label className="fld-label">Email</label>
          <input
            className="fld-input mb-5"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            data-testid="login-email"
            required
          />

          <label className="fld-label">Password</label>
          <input
            className="fld-input mb-7"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            data-testid="login-password"
            required
          />

          <button type="submit" disabled={loading} className="fld-btn-primary w-full" data-testid="login-submit">
            {loading ? "A ENTRAR..." : "ENTRAR"}
          </button>

          <div className="mt-6 text-sm text-[#A3A3A3]">
            Não tem conta?{" "}
            <Link to="/register" className="text-[#CCFF00] hover:underline" data-testid="goto-register">
              Criar conta
            </Link>
          </div>

          <div className="mt-10 p-4 border border-white/5 text-xs text-[#525252]">
            <div className="font-head tracking-widest text-[#A3A3A3] mb-1">VALIDAÇÃO</div>
            Novas contas precisam de ser validadas por um administrador antes do primeiro acesso.
          </div>
        </form>
      </div>
    </div>
  );
}
