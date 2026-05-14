import { Routes, Route, NavLink } from "react-router-dom";
import { BookOpen, BarChart3, GitCompare, FlaskConical, Home as HomeIcon } from "lucide-react";

import Home from "./pages/Home";
import Catalog from "./pages/Catalog";
import ModelViewer from "./pages/ModelViewer";
import Workshop from "./pages/Workshop";
import Compare from "./pages/Compare";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/models/:name" element={<ModelViewer />} />
          <Route path="/workshop" element={<Workshop />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

function Header() {
  const linkBase = "flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium";
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <NavLink to="/" className="flex items-baseline gap-2">
          <span className="font-serif text-2xl font-semibold text-wcn-primary">portopt</span>
          <span className="text-xs text-slate-500 italic">educacional</span>
        </NavLink>
        <nav className="flex items-center gap-1">
          {[
            { to: "/", icon: HomeIcon, label: "Início" },
            { to: "/catalog", icon: BookOpen, label: "Modelos" },
            { to: "/workshop", icon: FlaskConical, label: "Laboratório" },
            { to: "/compare", icon: GitCompare, label: "Comparar" },
          ].map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `${linkBase} ${isActive ? "bg-wcn-primary text-white" : "text-slate-700 hover:bg-slate-100"}`
              }
            >
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-6 text-sm text-slate-600">
        <p>
          <strong className="text-wcn-primary">portopt</strong> · WCN Softwares ·{" "}
          baseado no curso{" "}
          <em>Portfolio Optimization</em> do classical portfolio optimization literature.
        </p>
        <p className="mt-1 text-xs">
          Licença MIT · Educational use · Não constitui recomendação de investimento.
        </p>
      </div>
    </footer>
  );
}
