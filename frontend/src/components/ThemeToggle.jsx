import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export default function ThemeToggle({ testid = "theme-toggle" }) {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      data-testid={testid}
      title={`Mudar para tema ${isDark ? "claro" : "escuro"}`}
      aria-label={`Mudar para tema ${isDark ? "claro" : "escuro"}`}
      className="p-2 border border-white/10 hover:border-[#CCFF00]/60 hover:text-[#CCFF00] transition-colors"
    >
      {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
}
