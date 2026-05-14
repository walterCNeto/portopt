import { BlockMath } from "react-katex";
import type { PedagogyBlock as PedagogyData } from "../lib/api";

interface Props {
  data: PedagogyData;
}

export default function PedagogyBlock({ data }: Props) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-lg font-serif italic text-slate-700">{data.one_liner}</p>
      </div>

      {data.formula_latex && (
        <div className="rounded-md bg-slate-50 px-4 py-3 overflow-x-auto">
          <BlockMath math={data.formula_latex} />
        </div>
      )}

      <div className="ref-card">
        <strong>Onde aparece:</strong> {data.reference}
      </div>

      {data.when_to_use.length > 0 && (
        <Section title="Quando usar">
          <ul className="ml-5 list-disc space-y-1 text-sm">
            {data.when_to_use.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Section>
      )}

      {data.drawbacks.length > 0 && (
        <Section title="Limitações" color="text-rose-700">
          <ul className="ml-5 list-disc space-y-1 text-sm">
            {data.drawbacks.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Section>
      )}

      {data.references.length > 0 && (
        <Section title="Referências">
          <ul className="ml-5 list-disc space-y-1 text-xs text-slate-600">
            {data.references.map((s, i) => (
              <li key={i} className="font-mono">{s}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  color = "text-slate-800",
  children,
}: {
  title: string;
  color?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className={`mb-1 text-sm font-semibold uppercase tracking-wider ${color}`}>
        {title}
      </h4>
      {children}
    </div>
  );
}
