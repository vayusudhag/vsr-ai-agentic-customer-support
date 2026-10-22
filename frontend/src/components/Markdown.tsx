import { Fragment, type ReactNode } from "react";

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\])/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++} className="font-semibold">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("[")) out.push(<sup key={k++} className="ml-0.5 rounded bg-lagoon-soft px-1 text-[10px] font-semibold text-lagoon-ink">{t.slice(1, -1)}</sup>);
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Minimal, safe renderer for the assistant's markdown subset (no HTML injection). */
export function Markdown({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="space-y-2.5 leading-relaxed">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        const items = lines.filter((l) => l.startsWith("- "));
        const head = lines.filter((l) => !l.startsWith("- "));
        return (
          <Fragment key={i}>
            {head.length > 0 && <p>{inline(head.join(" "))}</p>}
            {items.length > 0 && (
              <ul className="space-y-1.5 pl-1">
                {items.map((l, j) => (
                  <li key={j} className="flex gap-2"><span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink/40" />
                    <span>{inline(l.slice(2))}</span></li>
                ))}
              </ul>
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
