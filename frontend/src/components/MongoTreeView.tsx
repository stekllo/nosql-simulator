/**
 * Раскрывающееся дерево документов MongoDB.
 *
 * Похоже на MongoDB Compass: каждый документ — корневой узел,
 * у которого внутри ключи и значения. Объекты и массивы раскрываются
 * по клику. Типы значений подсвечены цветом.
 */
import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";


export function MongoTreeView({ data }: { data: unknown }) {
  if (!Array.isArray(data)) {
    return <SingleValue value={data} />;
  }
  if (data.length === 0) {
    return <Empty />;
  }
  return (
    <div className="space-y-1 font-mono text-[12.5px]">
      {data.map((doc, i) => (
        <TreeNode key={i} keyName={`Документ ${i + 1}`} value={doc} initiallyOpen={i < 3} />
      ))}
    </div>
  );
}


interface NodeProps {
  keyName: string;
  value: unknown;
  initiallyOpen?: boolean;
}

function TreeNode({ keyName, value, initiallyOpen = false }: NodeProps) {
  const isObject = value !== null && typeof value === "object";
  const isArray  = Array.isArray(value);

  const [open, setOpen] = useState(initiallyOpen);

  if (!isObject) {
    return (
      <div className="flex items-baseline gap-2 pl-5">
        <span className="text-slate-700">"<span className="text-blue-700">{keyName}</span>":</span>
        <ScalarValue value={value} />
      </div>
    );
  }

  const entries = isArray
    ? (value as unknown[]).map((v, i) => [String(i), v] as const)
    : Object.entries(value as Record<string, unknown>);

  const summary = isArray
    ? `Array(${entries.length})`
    : `Object {${entries.length} ключ${pluralize(entries.length)}}`;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-baseline gap-1 hover:bg-slate-50 rounded px-1 w-full text-left"
      >
        <ChevronRight
          className={
            "w-3.5 h-3.5 text-slate-500 flex-shrink-0 transition-transform self-center " +
            (open ? "rotate-90" : "")
          }
        />
        <span className="text-slate-700">"<span className="text-blue-700 font-medium">{keyName}</span>":</span>
        {!open && <span className="text-slate-400 italic">{summary}</span>}
        {open && <span className="text-slate-500">{isArray ? "[" : "{"}</span>}
      </button>

      {open && (
        <>
          <div className="ml-4 pl-2 border-l border-slate-200">
            {entries.map(([k, v]) => (
              <TreeNode key={k} keyName={k} value={v} />
            ))}
          </div>
          <div className="pl-5 text-slate-500">{isArray ? "]" : "}"}</div>
        </>
      )}
    </div>
  );
}


function ScalarValue({ value }: { value: unknown }) {
  if (value === null)                    return <span className="text-slate-400">null</span>;
  if (typeof value === "string")         return <span className="text-emerald-700">"{value}"</span>;
  if (typeof value === "number")         return <span className="text-orange-600">{value}</span>;
  if (typeof value === "boolean")        return <span className="text-purple-700">{String(value)}</span>;
  return <span className="text-slate-600">{String(value)}</span>;
}


function SingleValue({ value }: { value: unknown }) {
  return (
    <div className="font-mono text-[12.5px] p-2">
      <ScalarValue value={value} />
    </div>
  );
}


function Empty(): ReactNode {
  return (
    <div className="text-sm text-slate-500 italic px-1 py-2">
      Запрос не вернул документов.
    </div>
  );
}


function pluralize(n: number): string {
  const last = n % 10;
  const teen = n % 100 >= 11 && n % 100 <= 14;
  if (teen)               return "ей";
  if (last === 1)         return "";
  if (last >= 2 && last <= 4) return "а";
  return "ей";
}
