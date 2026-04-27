import { Link, useParams } from "react-router-dom";
import { Clock, FileText, ChevronRight, CheckCircle2, Circle } from "lucide-react";

import { useCourse } from "@/hooks/useCourses";
import { nosqlTypeBadge, nosqlTypeLabel } from "@/lib/nosqlType";


export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { data: course, isLoading, isError } = useCourse(courseId);

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка курса…</div>;
  }
  if (isError || !course) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">Курс не найден.</div>;
  }

  const totalLessons = course.modules.reduce((sum, m) => sum + m.lessons.length, 0);
  const totalTasks   = course.modules.reduce(
    (sum, m) => sum + m.lessons.reduce((s2, l) => s2 + l.task_count, 0), 0,
  );

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">

      {/* Шапка курса */}
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">← Все курсы</Link>

        <div className="mt-3 flex items-center gap-2">
          <span className={
            "inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border font-mono " +
            nosqlTypeBadge[course.nosql_type]
          }>
            {nosqlTypeLabel[course.nosql_type]}
          </span>
          {course.difficulty != null && (
            <span className="text-xs text-slate-500">Сложность: {course.difficulty}/5</span>
          )}
        </div>

        <h1 className="text-[26px] font-semibold tracking-tight mt-2">{course.title}</h1>

        {course.description && (
          <p className="text-sm text-slate-600 mt-2 leading-relaxed max-w-2xl">
            {course.description}
          </p>
        )}

        <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
          <span>Автор: <b className="text-slate-900 font-medium">{course.author.display_name ?? course.author.login}</b></span>
          <span>•</span>
          <span>{course.modules.length} модулей</span>
          <span>•</span>
          <span>{totalLessons} уроков</span>
          <span>•</span>
          <span>{totalTasks} заданий</span>
        </div>

        {/* Прогресс-бар */}
        {course.progress && course.progress.lessons_total > 0 && (
          <div className="mt-5 bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium text-slate-900">
                Ваш прогресс
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-semibold text-slate-900">{course.progress.lessons_completed}</span>
                <span className="text-slate-500"> / {course.progress.lessons_total} уроков</span>
                {course.progress.tasks_total > 0 && (
                  <span className="text-slate-400 ml-3">
                    {course.progress.tasks_solved} / {course.progress.tasks_total} заданий
                  </span>
                )}
              </div>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={
                  "h-full rounded-full transition-all duration-500 " +
                  (course.progress.percent === 100 ? "bg-emerald-500" : "bg-blue-500")
                }
                style={{ width: `${course.progress.percent}%` }}
              />
            </div>
            <div className="text-[11px] text-slate-500 mt-1.5">
              {course.progress.percent === 100
                ? "🎉 Курс пройден полностью"
                : `${course.progress.percent}% курса пройдено`}
            </div>
          </div>
        )}
      </div>

      {/* Модули */}
      <div className="mt-8 space-y-4">
        {course.modules.map((m) => (
          <section
            key={m.module_id}
            className="bg-white rounded-lg border border-slate-200 overflow-hidden"
          >
            <header className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/50">
              <div className="text-[11px] text-slate-500 uppercase tracking-wider">
                Модуль {m.order_num}
              </div>
              <div className="text-[15px] font-semibold mt-0.5">{m.title}</div>
              {m.description && (
                <div className="text-xs text-slate-500 mt-1">{m.description}</div>
              )}
            </header>

            <ul className="divide-y divide-slate-100">
              {m.lessons.map((lesson) => (
                <li key={lesson.lesson_id}>
                  <Link
                    to={`/lessons/${lesson.lesson_id}`}
                    className="flex items-center gap-4 px-5 py-3 hover:bg-slate-50 transition-colors"
                  >
                    {/* Иконка прогресса вместо номера + сам номер маленьким текстом */}
                    {lesson.is_completed ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                    ) : (
                      <Circle className="w-5 h-5 text-slate-300 flex-shrink-0" />
                    )}
                    <span className="text-xs font-mono text-slate-400 w-6 text-right">
                      {lesson.order_num}.
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className={
                        "text-sm font-medium truncate " +
                        (lesson.is_completed ? "text-slate-600" : "text-slate-900")
                      }>
                        {lesson.title}
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-0.5">
                        {lesson.duration_min != null && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {lesson.duration_min} мин
                          </span>
                        )}
                        {lesson.task_count > 0 && (
                          <span className="flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {lesson.task_count} {lesson.task_count === 1 ? "задание" : "заданий"}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

    </div>
  );
}
