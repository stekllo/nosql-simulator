import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Clock, FileText, CheckCircle2, Circle, ArrowRight, Loader2 } from "lucide-react";

import { useCompleteLesson, useLesson } from "@/hooks/useCourses";


export function LessonPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const navigate     = useNavigate();
  const { data: lesson, isLoading, isError } = useLesson(lessonId);
  const completeLesson = useCompleteLesson();

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка урока…</div>;
  }
  if (isError || !lesson) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">Урок не найден.</div>;
  }

  // Подсчитываем решённые задания для шапки урока.
  const solvedCount    = lesson.tasks.filter(t => t.is_solved).length;
  const totalCount     = lesson.tasks.length;
  const allTasksSolved = totalCount === 0 || solvedCount === totalCount;

  // Обработчик кнопки «Дальше →».
  // Логика:
  // - Если урок ещё не помечен пройденным И (заданий нет ИЛИ все решены)
  //   → отправляем POST /complete и переходим.
  // - В остальных случаях — просто переходим (отметка не нужна или
  //   ставить её преждевременно, потому что задания не решены).
  const handleNext = async () => {
    if (!lesson.is_completed && allTasksSolved) {
      try {
        await completeLesson.mutateAsync(lesson.lesson_id);
      } catch {
        // Если не получилось — всё равно переходим, отметку поставим в другой раз.
      }
    }
    if (lesson.next_lesson_id) {
      navigate(`/lessons/${lesson.next_lesson_id}`);
    } else {
      // Это последний урок курса. Возвращаемся назад через history —
      // обычно это страница курса, с которой студент пришёл.
      navigate(-1);
    }
  };

  // Текст кнопки «Дальше →».
  const buttonLabel = (() => {
    if (lesson.is_completed) {
      return lesson.next_lesson_id ? "Дальше" : "Завершить курс";
    }
    if (!allTasksSolved) {
      // Есть нерешённые задания — позволяем пропустить, но без отметки.
      return lesson.next_lesson_id ? "Пропустить, дальше" : "На страницу курса";
    }
    // Можно отметить как пройденный.
    return lesson.next_lesson_id ? "Я прочитал, дальше" : "Завершить курс";
  })();

  // Стиль: синяя кнопка для действия пометки, белая для просто навигации.
  const buttonPrimary = !lesson.is_completed && allTasksSolved;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">

      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
        ← Вернуться в каталог
      </Link>

      <div className="mt-3">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="text-[11px] uppercase tracking-wider">Урок {lesson.order_num}</span>
          {lesson.is_completed && (
            <span className="flex items-center gap-1 text-emerald-700 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Пройден
            </span>
          )}
          {lesson.duration_min != null && (
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {lesson.duration_min} мин
            </span>
          )}
          {totalCount > 0 && (
            <span className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" />
              {solvedCount} / {totalCount} {totalCount === 1 ? "задание" : "заданий"} решено
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

      {totalCount > 0 && (
        <section className="mt-8">
          <h2 className="text-[15px] font-semibold mb-3">Практические задания</h2>
          <div className="space-y-3">
            {lesson.tasks.map((task, idx) => (
              <div key={task.task_id}
                   className={
                     "bg-white rounded-lg border p-5 " +
                     (task.is_solved ? "border-emerald-200" : "border-slate-200")
                   }>
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
                  {task.is_solved ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  )}
                  <span className="font-medium uppercase tracking-wide">
                    Задание {lesson.order_num}.{idx + 1}
                  </span>
                  <span>•</span>
                  <span>{task.max_score} баллов</span>
                  {task.is_solved && (
                    <>
                      <span>•</span>
                      <span className="text-emerald-700 font-medium">Решено</span>
                    </>
                  )}
                </div>
                <p className="text-sm text-slate-900 leading-relaxed">{task.statement}</p>

                <Link
                  to={`/tasks/${task.task_id}`}
                  className={
                    "inline-block mt-3 px-3 py-1.5 text-xs rounded font-medium " +
                    (task.is_solved
                      ? "text-slate-700 bg-white border border-slate-300 hover:bg-slate-50"
                      : "text-white bg-blue-600 hover:bg-blue-700")
                  }
                >
                  {task.is_solved ? "Открыть снова" : "Открыть редактор"}
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Кнопка «Дальше →» */}
      <div className="mt-8 flex items-center justify-between gap-4 flex-wrap">
        <div className="text-xs text-slate-500 max-w-md">
          {!lesson.is_completed && !allTasksSolved && (
            <>
              Чтобы получить отметку о прохождении, решите все задания этого
              урока. Можно пропустить и вернуться позже.
            </>
          )}
          {!lesson.is_completed && allTasksSolved && totalCount === 0 && (
            <>Нажмите «Я прочитал, дальше», когда закончите изучать материал.</>
          )}
          {lesson.is_completed && (
            <>Урок уже отмечен как пройденный. Можно перейти к следующему.</>
          )}
        </div>
        <button
          type="button"
          onClick={handleNext}
          disabled={completeLesson.isPending}
          className={
            "flex items-center gap-2 px-5 py-2.5 text-sm rounded font-medium disabled:opacity-60 " +
            (buttonPrimary
              ? "text-white bg-blue-600 hover:bg-blue-700"
              : "text-slate-700 bg-white border border-slate-300 hover:bg-slate-50")
          }
        >
          {completeLesson.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : null}
          {buttonLabel}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

    </div>
  );
}
