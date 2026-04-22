import { useMe } from "@/hooks/useAuth";

export function HomePage() {
  const { data: user } = useMe();

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">

      <h1 className="text-[26px] font-semibold tracking-tight">
        Добро пожаловать{user?.display_name ? `, ${user.display_name}` : ""}!
      </h1>
      <p className="text-sm text-slate-500 mt-1">
        Каталог курсов и обучение появятся здесь в следующих обновлениях.
      </p>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          { title: "MongoDB для начинающих", type: "DOCUMENT",  color: "green"  },
          { title: "Redis: кэш и структуры", type: "KEY-VALUE", color: "rose"   },
          { title: "Cassandra: большие данные", type: "COLUMN", color: "purple" },
          { title: "Neo4j и язык Cypher",    type: "GRAPH",     color: "blue"   },
        ].map((c) => (
          <div
            key={c.title}
            className="bg-white rounded-lg border border-slate-200 p-5 hover:shadow-md transition-shadow"
          >
            <div className={`inline-block text-[10px] mono font-semibold px-1.5 py-0.5 rounded border bg-${c.color}-50 text-${c.color}-700 border-${c.color}-200`}>
              {c.type}
            </div>
            <div className="mt-2 text-[15px] font-medium">{c.title}</div>
            <div className="text-xs text-slate-500 mt-1">
              Скоро будет доступен
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
