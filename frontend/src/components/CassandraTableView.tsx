/**
 * Табличный вид результата CQL-запроса — как в cqlsh.
 *
 * Cassandra — колоночная БД, и её данные естественно ложатся в таблицу
 * с фиксированными колонками. Каждая строка результата — это row из
 * cassandra-driver, представленный как объект {column_name: value}.
 */


export function CassandraTableView({ data }: { data: unknown }) {
  if (!Array.isArray(data) || data.length === 0) {
    return <Empty />;
  }

  const first = data[0];
  if (first === null || typeof first !== "object") {
    return <Empty />;
  }

  const columns = Object.keys(first as Record<string, unknown>);

  return (
    <div className="bg-white border border-cyan-100 rounded-lg overflow-hidden">
      <div className="overflow-x-auto max-h-80">
        <table className="w-full font-mono text-[12.5px]">
          <thead className="sticky top-0">
            <tr className="bg-[#1287B1] text-white">
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-semibold border border-[#1287B1]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-cyan-50/50"}>
                {columns.map(col => (
                  <td
                    key={col}
                    className="px-3 py-2 border border-cyan-100 text-slate-800 whitespace-nowrap"
                  >
                    {formatCell((row as Record<string, unknown>)[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-1.5 text-[11px] text-slate-500 border-t border-cyan-100 bg-cyan-50/30">
        {data.length} строк
      </div>
    </div>
  );
}


function formatCell(v: unknown): string {
  if (v === null || v === undefined)  return "—";
  if (typeof v === "string")          return v;
  if (typeof v === "number")          return String(v);
  if (typeof v === "boolean")         return v ? "true" : "false";
  return JSON.stringify(v);
}


function Empty() {
  return (
    <div className="text-sm text-slate-500 italic px-1 py-2">
      Запрос не вернул строк.
    </div>
  );
}
