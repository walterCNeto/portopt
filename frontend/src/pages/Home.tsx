import { Link } from "react-router-dom";
import { BookOpen, FlaskConical, GitCompare } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="text-center">
        <h1 className="font-serif text-5xl font-semibold leading-tight text-wcn-ink">
          Otimização de portfólios,
          <br />
          <span className="text-wcn-primary">do mais simples ao mais complexo.</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Plataforma educacional de otimização de portfólios. Explore
          13 modelos da literatura clássica — de Markowitz a Hierarchical Risk Parity —
          com fórmulas em LaTeX, referências bibliográficas e comparativos lado a lado.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link to="/catalog" className="btn btn-primary">
            Ver catálogo de modelos
          </Link>
          <Link to="/workshop" className="btn btn-secondary">
            Ir ao laboratório
          </Link>
        </div>
      </section>

      {/* Three pillars */}
      <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Pillar
          icon={<BookOpen size={32} className="text-tier-allocation" />}
          title="Catálogo"
          description="16 modelos organizados em 5 tiers de complexidade. Cada um com fórmula, referência ao paper original e drawbacks conhecidos."
          to="/catalog"
        />
        <Pillar
          icon={<FlaskConical size={32} className="text-tier-risk_budget" />}
          title="Laboratório"
          description="Carregue dados de mercado (yfinance, BACEN ou datasets curados) e rode otimização + backtest com custos brasileiros realistas."
          to="/workshop"
        />
        <Pillar
          icon={<GitCompare size={32} className="text-tier-robust" />}
          title="Comparativo"
          description="O killer feature: rode N modelos no mesmo dataset, veja pesos, métricas e wealth paths lado a lado. Ideal para entender diferenças."
          to="/compare"
        />
      </section>

      {/* Datasets bundled */}
      <section className="rounded-lg bg-white p-6 shadow-sm">
        <h2 className="mb-3 font-serif text-2xl font-semibold">
          Datasets educacionais inclusos
        </h2>
        <p className="mb-4 text-sm text-slate-600">
          Os três datasets originais do curso são distribuídos com a plataforma e
          podem ser usados sem cadastro:
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <DatasetTile
            name="ex1"
            title="24 ações brasileiras + CDI"
            period="2003-12 → 2023-12"
            exercise="nb1 — MV vs EW backtest"
          />
          <DatasetTile
            name="mdr"
            title="24 commodity futures"
            period="2012-12 → 2023-12"
            exercise="nb2 — Mean-Downside-Risk"
          />
          <DatasetTile
            name="mcvar"
            title="24 commodity futures"
            period="2012-12 → 2023-12"
            exercise="nb2 — Mean-CVaR"
          />
        </div>
      </section>
    </div>
  );
}

function Pillar({
  icon,
  title,
  description,
  to,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  to: string;
}) {
  return (
    <Link to={to} className="model-card text-left">
      <div className="mb-3">{icon}</div>
      <h3 className="mb-2 font-serif text-xl font-semibold">{title}</h3>
      <p className="text-sm text-slate-600">{description}</p>
    </Link>
  );
}

function DatasetTile({
  name,
  title,
  period,
  exercise,
}: {
  name: string;
  title: string;
  period: string;
  exercise: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="mb-1 flex items-center gap-2">
        <code className="rounded bg-wcn-primary px-2 py-0.5 text-xs text-white">
          {name}
        </code>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-xs text-slate-500">{period}</p>
      <p className="text-xs italic text-slate-500">{exercise}</p>
    </div>
  );
}
