/**
 * Страница одного курса в конструкторе: дерево модулей/уроков/заданий,
 * рядом с каждым уроком — кнопки «Урок» и «+ Задание»,
 * под уроком — список заданий с кнопкой «Изменить» у каждого.
 * В шапке каждого модуля — кнопка «+ Урок».
 */
import { Link, useParams } from "react-router-dom";
import { FileText, Plus, Clock, BookOpen, Pencil } from "lucide-react";

import { useBuilderCourse } from "@/hooks/useBuilder";
import { nosqlTypeBadge, nosqlTypeLabel } from "@/lib/nosqlType";


export function BuilderCoursePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { data: course, isLoading } = useBuilderCourse(courseId);

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка…</div>;
  }
  if (!course) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">Курс не найден.</div>;
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">

      <Link to="/builder" className="text-sm text-slate-500 hover:text-slate-900">
        ← К списку курсов
      </Link>

      <div className="mt-3 flex items-center gap-2">
        <span className={
          "inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border font-mono " +
          nosqlTypeBadge[course.nosql_type]
        }>
          {nosqlTypeLabel[course.nosql_type]}
        </span>
        <span className="text-xs text-slate-500 uppercase tracking-wider">Редактирование</span>
      </div>

      <h1 className="text-[24px] font-semibold tracking-tight mt-2">{course.title}</h1>

      {course.description && (
        <p className="text-sm text-slate-600 mt-2 leading-relaxed max-w-2xl">{course.description}</p>
      )}

      {/* Модули */}
      <div className="mt-8 space-y-4">
        {course.modules.length === 0 && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 text-center text-sm text-slate-500">
            В курсе ещё нет модулей. Создание модулей из UI появится в следующем обновлении
            (пока добавляйте через <code className="font-mono">scripts/seed.py</code>).
          </div>
        )}

        {course.modules.map((m) => {
          // Следующий свободный order_num для нового урока в этом модуле.
          const nextOrder = m.lessons.length > 0
            ? Math.max(...m.lessons.map(l => l.order_num)) + 1
            : 1;

          return (
            <section key={m.module_id}
                     className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <header className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/50 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">
                    Модуль {m.order_num}
                  </div>
                  <div className="text-[15px] font-semibold mt-0.5">{m.title}</div>
                </div>
                <Link
                  to={`/builder/modules/${m.module_id}/lessons/new?order=${nextOrder}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded font-medium flex-shrink-0"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Урок
                </Link>
              </header>

              <ul className="divide-y divide-slate-100">
                {m.lessons.map((lesson) => (
                  <li key={lesson.lesson_id} className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <BookOpen className="w-4 h-4 text-slate-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <Link
                          to={`/builder/lessons/${lesson.lesson_id}/edit`}
                          className="text-sm font-medium text-slate-900 hover:text-blue-700 truncate block"
                        >
                          {lesson.order_num}. {lesson.title}
                        </Link>
                        <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-0.5">
                          {lesson.duration_min != null && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {lesson.duration_min} мин
                            </span>
                          )}
                          <span className="flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {lesson.tasks.length} {lesson.tasks.length === 1 ? "задание" : "заданий"}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Link
                          to={`/builder/lessons/${lesson.lesson_id}/edit`}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded font-medium"
                          title="Редактировать урок (Markdown)"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                          Урок
                        </Link>
                        <Link
                          to={`/builder/lessons/${lesson.lesson_id}/tasks/new`}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-blue-600 hover:bg-blue-700 rounded font-medium"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          Задание
                        </Link>
                      </div>
                    </div>

                    {/* Список заданий урока (если есть) */}
                    {lesson.tasks.length > 0 && (
                      <ul className="mt-2 ml-7 space-y-1">
                        {lesson.tasks.map((t, idx) => (
                          <li key={t.task_id}
                              className="flex items-center gap-2 text-[12px] text-slate-600 group">
                            <span className="font-mono text-slate-400 flex-shrink-0">
                              {lesson.order_num}.{idx + 1}
                            </span>
                            <span className="flex-1 min-w-0 truncate" title={t.statement}>
                              {t.statement}
                            </span>
                            <span className="flex-shrink-0 text-[10px] text-slate-400">
                              {t.max_score} б.
                            </span>
                            <Link
                              to={`/builder/tasks/${t.task_id}/edit`}
                              className="flex-shrink-0 px-2 py-0.5 text-[11px] text-slate-600 hover:text-blue-700 hover:bg-blue-50 rounded font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Открыть задание для редактирования (включая эталон)"
                            >
                              <Pencil className="w-3 h-3 inline mr-0.5" />
                              Изменить
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
                {m.lessons.length === 0 && (
                  <li className="px-5 py-4 text-xs text-slate-500">
                    В модуле ещё нет уроков. Нажмите «+ Урок» в шапке модуля, чтобы добавить.
                  </li>
                )}
              </ul>
            </section>
          );
        })}
      </div>

    </div>
  );
}
