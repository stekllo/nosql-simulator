import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

import { useMe }      from "@/hooks/useAuth";
import { useCourses } from "@/hooks/useCourses";
import { nosqlTypeLabel, nosqlTypeBadge } from "@/lib/nosqlType";
import type { NoSQLType } from "@/lib/types";


const FILTERS: Array<{ value: NoSQLType | null; label: string }> = [
  { value: null,         label: "Все"       },
  { value: "document",   label: "Document"  },
  { value: "key_value",  label: "Key-Value" },
  { value: "column",     label: "Column"    },
  { value: "graph",      label: "Graph"     },
];


export function HomePage() {
  const { data: user }         = useMe();
  const [filter, setFilter]    = useState<NoSQLType | null>(null);
  const { data: courses, isLoading, isError } = useCourses({ nosqlType: filter });

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">

      <header>
        <h1 className="text-[26px] font-semibold tracking-tight">
          Добро пожаловать{user?.display_name ? `, ${user.display_name}` : ""}!
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Выберите курс, чтобы начать обучение.
        </p>
      </header>

      {/* Фильтр по типу СУБД */}
      <div className="mt-6 flex items-center gap-1 bg-white border border-slate-200 rounded-md p-1 w-fit">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => setFilter(f.value)}
            className={
              "px-3 py-1.5 rounded text-sm transition-colors " +
              (filter === f.value
                ? "bg-slate-100 text-slate-900 font-medium"
                : "text-slate-600 hover:bg-slate-50")
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Список курсов */}
      <div className="mt-6">
        {isLoading && <div className="text-sm text-slate-500">Загрузка курсов…</div>}

        {isError && (
          <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-md p-3">
            Не удалось загрузить курсы. Проверьте подключение к серверу.
          </div>
        )}

        {courses && courses.length === 0 && (
          <div className="text-sm text-slate-500">
            Курсов такого типа пока нет.
          </div>
        )}

        {courses && courses.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {courses.map((c) => {
              const completed = c.progress?.percent === 100;
              return (
                <Link
                  key={c.course_id}
                  to={`/courses/${c.course_id}`}
                  className="block bg-white rounded-lg border border-slate-200 p-5 hover:shadow-md hover:border-slate-300 transition relative"
                >
                  <div className="flex items-center gap-2">
                    <div className={
                      "inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border font-mono " +
                      nosqlTypeBadge[c.nosql_type]
                    }>
                      {nosqlTypeLabel[c.nosql_type]}
                    </div>
                    {completed && (
                      <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                        <CheckCircle2 className="w-3 h-3" />
                        Пройден
                      </span>
                    )}
                  </div>

                  <div className="mt-2 text-[15px] font-semibold leading-snug">
                    {c.title}
                  </div>

                  {c.description && (
                    <div className="text-xs text-slate-500 mt-2 line-clamp-3 leading-relaxed">
                      {c.description}
                    </div>
                  )}

                  <div className="mt-3 flex items-center gap-3 text-[11px] text-slate-500">
                    <span>Автор: {c.author.display_name ?? c.author.login}</span>
                    {c.difficulty != null && (
                      <>
                        <span>•</span>
                        <span>Сложность: {c.difficulty}/5</span>
                      </>
                    )}
                  </div>

                  {/* Прогресс */}
                  {c.progress && c.progress.lessons_total > 0 && (
                    <div className="mt-4 pt-3 border-t border-slate-100">
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
                        <span>
                          {c.progress.lessons_completed} / {c.progress.lessons_total} уроков
                        </span>
                        <span className="font-medium text-slate-700">
                          {c.progress.percent}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={
                            "h-full rounded-full " +
                            (completed ? "bg-emerald-500" : "bg-blue-500")
                          }
                          style={{ width: `${c.progress.percent}%` }}
                        />
                      </div>
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
