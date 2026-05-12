/**
 * Универсальный табличный вид для скалярных результатов.
 *
 * Используется для Neo4j-запросов вида `RETURN p.name, p.age` — когда
 * Cypher возвращает не узлы, а скалярные значения. Также fallback
 * для типа `mixed`.
 */

export function GenericTableView({ data }: { data: unknown }) {
  if (!Array.isArray(data) || data.length === 0) {
    return <Empty />;
  }
  const first = data[0];
  if (first === null || typeof first !== "object" || Array.isArray(first)) {
    return (
      <pre className="text-[12.5px] font-mono text-slate-800 whitespace-pre-wrap bg-slate-50 rounded p-3 border border-slate-200 overflow-auto max-h-80">
        {JSON.stringify(data, null, 2)}
      </pre>
    );
  }

  const columns = Object.keys(first as Record<string, unknown>);
  if (columns.length === 0) {
    return <Empty />;
  }

  return (
    <div className="bg-white border border-blue-100 rounded-lg overflow-hidden">
      <div className="overflow-x-auto max-h-80">
        <table className="w-full font-mono text-[12.5px]">
          <thead className="sticky top-0">
            <tr className="bg-[#018BFF] text-white">
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-semibold border border-[#018BFF]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-blue-50/40"}>
                {columns.map(col => (
                  <td
                    key={col}
                    className="px-3 py-2 border border-blue-100 text-slate-800"
                  >
                    {formatCell((row as Record<string, unknown>)[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-1.5 text-[11px] text-slate-500 border-t border-blue-100 bg-blue-50/20">
        {data.length} записей
      </div>
    </div>
  );
}


function formatCell(v: unknown): string {
  if (v === null || v === undefined)  return "—";
  if (typeof v === "string")          return v;
  if (typeof v === "number")          return String(v);
  if (typeof v === "boolean")         return v ? "true" : "false";
  if (typeof v === "object")          return JSON.stringify(v);
  return String(v);
}


function Empty() {
  return (
    <div className="text-sm text-slate-500 italic px-1 py-2">
      Запрос не вернул данных.
    </div>
  );
}
