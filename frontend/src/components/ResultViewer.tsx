/**
 * Универсальный отображатель результатов запросов NoSQL-СУБД.
 *
 * Содержит переключатель «Просмотр / JSON» в верхней части и
 * автоматически выбирает подходящее представление под тип СУБД:
 *
 *   - document  → раскрывающееся дерево документов (как в MongoDB Compass)
 *   - key_value → карточки ключей с цветными бейджами типов (как в Redis CLI)
 *   - column    → табличный вид (как в cqlsh)
 *   - graph     → таблица, если возвращены скаляры; иначе JSON
 *
 * Для всех случаев пользователь может переключиться на сырой JSON
 * одним кликом — это «правда от драйвера», полезно для отладки и
 * для понимания контракта реального API.
 */
import { useState } from "react";
import { Code2, LayoutGrid } from "lucide-react";
import type { NoSQLType } from "@/lib/types";

import { MongoTreeView } from "./MongoTreeView";
import { RedisCardsView } from "./RedisCardsView";
import { CassandraTableView } from "./CassandraTableView";
import { GenericTableView } from "./GenericTableView";


type ResultData = unknown;

interface Props {
  result:  ResultData;
  dbType:  NoSQLType;
  className?: string;
}


export function ResultViewer({ result, dbType, className = "" }: Props) {
  const [mode, setMode] = useState<"pretty" | "json">("pretty");

  const PrettyView = (() => {
    switch (dbType) {
      case "document":  return <MongoTreeView      data={result} />;
      case "key_value": return <RedisCardsView     data={result} />;
      case "column":    return <CassandraTableView data={result} />;
      case "graph":
      case "mixed":
      default:
        return <GenericTableView data={result} />;
    }
  })();

  return (
    <div className={className}>
      <div className="flex items-center gap-1 px-1 py-1 bg-slate-100 rounded-md w-fit text-xs">
        <button
          type="button"
          onClick={() => setMode("pretty")}
          className={
            "flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors " +
            (mode === "pretty"
              ? "bg-white text-slate-900 shadow-sm font-medium"
              : "text-slate-600 hover:text-slate-900")
          }
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          Просмотр
        </button>
        <button
          type="button"
          onClick={() => setMode("json")}
          className={
            "flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors " +
            (mode === "json"
              ? "bg-white text-slate-900 shadow-sm font-medium"
              : "text-slate-600 hover:text-slate-900")
          }
        >
          <Code2 className="w-3.5 h-3.5" />
          JSON
        </button>
      </div>

      <div className="mt-2">
        {mode === "pretty"
          ? PrettyView
          : <JsonView data={result} />
        }
      </div>
    </div>
  );
}


function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="text-[12.5px] font-mono text-slate-800 whitespace-pre-wrap bg-slate-50 rounded p-3 border border-slate-200 overflow-auto max-h-80">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
