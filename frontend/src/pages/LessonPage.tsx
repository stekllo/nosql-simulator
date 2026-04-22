import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Clock, FileText } from "lucide-react";

import { useLesson } from "@/hooks/useCourses";


export function LessonPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const { data: lesson, isLoading, isError } = useLesson(lessonId);

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка урока…</div>;
  }
  if (isError || !lesson) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">Урок не найден.</div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">

      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
        ← Вернуться в каталог
      </Link>

      <div className="mt-3">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="text-[11px] uppercase tracking-wider">Урок {lesson.order_num}</span>
          {lesson.duration_min != null && (
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {lesson.duration_min} мин
            </span>
          )}
          {lesson.tasks.length > 0 && (
            <span className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" />
              {lesson.tasks.length} заданий
            </span>
          )}
        </div>
      </div>

      <article className="mt-6 bg-white rounded-lg border border-slate-200 p-8">
        <div className="prose-lesson">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {lesson.content_md}
          </ReactMarkdown>
        </div>
      </article>

      {lesson.tasks.length > 0 && (
        <section className="mt-8">
          <h2 className="text-[15px] font-semibold mb-3">Практические задания</h2>
          <div className="space-y-3">
            {lesson.tasks.map((task, idx) => (
              <div key={task.task_id}
                   className="bg-white rounded-lg border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
                  <span className="font-medium uppercase tracking-wide">
                    Задание {lesson.order_num}.{idx + 1}
                  </span>
                  <span>•</span>
                  <span>{task.max_score} баллов</span>
                </div>
                <p className="text-sm text-slate-900 leading-relaxed">{task.statement}</p>

                <Link
                  to={`/tasks/${task.task_id}`}
                  className="inline-block mt-3 px-3 py-1.5 text-xs text-white bg-blue-600 hover:bg-blue-700 rounded font-medium"
                >
                  Открыть редактор
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  );
}
