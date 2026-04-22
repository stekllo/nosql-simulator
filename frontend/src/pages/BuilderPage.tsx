/**
 * Главная страница конструктора: список курсов текущего преподавателя.
 */
import { Link } from "react-router-dom";
import { Plus, BookOpen, ChevronRight } from "lucide-react";

import { useMyCourses } from "@/hooks/useBuilder";
import { nosqlTypeBadge, nosqlTypeLabel } from "@/lib/nosqlType";


export function BuilderPage() {
  const { data: courses, isLoading } = useMyCourses();

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">

      <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight">
            Конструктор заданий
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Управляйте своими курсами, добавляйте новые модули, уроки и практические задания.
          </p>
        </div>
      </div>

      {isLoading && <div className="text-sm text-slate-500">Загрузка…</div>}

      {courses && courses.length === 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
          <BookOpen className="w-10 h-10 mx-auto text-slate-300" />
          <div className="mt-3 text-sm font-medium text-slate-900">У вас ещё нет курсов</div>
          <div className="text-xs text-slate-500 mt-1">
            Создание новых курсов появится в следующем обновлении.<br />
            Пока работайте с существующими — добавляйте к ним модули и задания.
          </div>
        </div>
      )}

      {courses && courses.length > 0 && (
        <div className="space-y-3">
          {courses.map((c) => (
            <Link
              key={c.course_id}
              to={`/builder/courses/${c.course_id}`}
              className="block bg-white rounded-lg border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className={
                  "inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border font-mono " +
                  nosqlTypeBadge[c.nosql_type]
                }>
                  {nosqlTypeLabel[c.nosql_type]}
                </span>
                {c.difficulty != null && (
                  <span className="text-xs text-slate-500">Сложность: {c.difficulty}/5</span>
                )}
                <ChevronRight className="ml-auto w-4 h-4 text-slate-400" />
              </div>
              <div className="text-[15px] font-semibold text-slate-900">{c.title}</div>
              {c.description && (
                <div className="text-xs text-slate-500 mt-2 line-clamp-2">{c.description}</div>
              )}
            </Link>
          ))}
        </div>
      )}

    </div>
  );
}
