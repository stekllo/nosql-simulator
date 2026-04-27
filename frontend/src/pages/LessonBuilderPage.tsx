/**
 * Конструктор урока: создание и редактирование Markdown-контента.
 *
 * Маршруты:
 *   /builder/modules/:moduleId/lessons/new   — режим создания
 *   /builder/lessons/:lessonId/edit          — режим редактирования
 *
 * Слева: метаданные урока + Monaco-редактор Markdown.
 * Справа: live-preview через ReactMarkdown (тот же стиль, что у студента).
 *
 * После успешного сохранения возвращает на страницу курса в конструкторе.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useForm, type FieldErrors, type UseFormRegister } from "react-hook-form";
import Editor from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Save, Loader2, Eye, Code as CodeIcon, AlertCircle, Trash2,
} from "lucide-react";

import {
  useCreateLesson, useDeleteLesson, useLessonForEdit, useUpdateLesson,
} from "@/hooks/useBuilder";
import { extractErrorMessage } from "@/lib/api";


interface FormFields {
  title:        string;
  order_num:    number;
  duration_min: number | null;
}


const STARTER_CONTENT = `# Заголовок урока

Краткое введение: что студент изучит и зачем это нужно.

## Теория

Объясните ключевые понятия. Используйте **жирный** для важных терминов и *курсив* для акцентов.

### Подзаголовок

Списки помогают структурировать материал:

- Первый пункт
- Второй пункт
- Третий пункт

## Пример

Покажите запрос на практике:

\`\`\`javascript
db.users.find({ age: { $gte: 18 } })
\`\`\`

## Итог

Краткое резюме урока в одном-двух абзацах.
`;


// =======================================================================
// Главный компонент: роутится по двум маршрутам
// =======================================================================

export function LessonBuilderPage() {
  const params = useParams<{ lessonId?: string; moduleId?: string }>();

  // Режим определяем по наличию параметра.
  if (params.lessonId) {
    return <EditLessonView lessonId={Number(params.lessonId)} />;
  }
  if (params.moduleId) {
    return <NewLessonView moduleId={Number(params.moduleId)} />;
  }
  return (
    <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">
      Некорректный URL.
    </div>
  );
}


// =======================================================================
// Режим: создание нового урока
// =======================================================================

function NewLessonView({ moduleId }: { moduleId: number }) {
  const navigate     = useNavigate();
  const [searchParams] = useSearchParams();
  const createLesson = useCreateLesson(moduleId);

  // Если страница открыта по «+ Урок» из BuilderCoursePage, она прокидывает
  // следующий свободный order_num через query (?order=N).
  const suggestedOrder = Math.max(1, Number(searchParams.get("order")) || 1);

  const [content, setContent] = useState(STARTER_CONTENT);

  const { register, handleSubmit, formState: { errors } } = useForm<FormFields>({
    defaultValues: {
      title:        "",
      order_num:    suggestedOrder,
      duration_min: 15,
    },
  });

  const onSave = handleSubmit(async (fields) => {
    try {
      const lesson = await createLesson.mutateAsync({
        title:        fields.title,
        content_md:   content,
        order_num:    fields.order_num,
        duration_min: fields.duration_min ?? null,
      });
      // После создания возвращаем в редактор курса.
      // courseId не знаем напрямую, но createLesson инвалидирует кэш — этого хватит.
      navigate(`/builder/lessons/${lesson.lesson_id}/edit`, { replace: true });
    } catch {
      /* ошибка отобразится через createLesson.error */
    }
  });

  return (
    <LessonEditorShell
      heading="Новый урок"
      subheading="Заполните метаданные и напишите содержимое в Markdown."
      backLink={null}
      content={content}
      setContent={setContent}
      register={register}
      errors={errors}
      onSave={onSave}
      saving={createLesson.isPending}
      saveError={createLesson.isError ? extractErrorMessage(createLesson.error) : null}
      saveSuccess={false}
      onDelete={null}
    />
  );
}


// =======================================================================
// Режим: редактирование существующего урока
// =======================================================================

function EditLessonView({ lessonId }: { lessonId: number }) {
  const navigate     = useNavigate();
  const { data: lesson, isLoading, isError, error } = useLessonForEdit(lessonId);
  const updateLesson = useUpdateLesson(lessonId);
  const deleteLesson = useDeleteLesson();

  const [content,     setContent]     = useState<string>("");
  const [savedAt,     setSavedAt]     = useState<Date | null>(null);
  const [confirmDel,  setConfirmDel]  = useState(false);

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormFields>({
    defaultValues: { title: "", order_num: 1, duration_min: null },
  });

  // Подгружаем данные урока в форму, когда они приехали с бэка.
  useEffect(() => {
    if (lesson) {
      setContent(lesson.content_md);
      reset({
        title:        lesson.title,
        order_num:    lesson.order_num,
        duration_min: lesson.duration_min,
      });
    }
  }, [lesson, reset]);

  const onSave = handleSubmit(async (fields) => {
    try {
      await updateLesson.mutateAsync({
        title:        fields.title,
        content_md:   content,
        order_num:    fields.order_num,
        duration_min: fields.duration_min ?? null,
      });
      setSavedAt(new Date());
    } catch {
      /* ошибка отобразится через updateLesson.error */
    }
  });

  const onDelete = async () => {
    if (!confirmDel) {
      setConfirmDel(true);
      // Через 4 секунды снимаем подтверждение, если не нажали ещё раз.
      setTimeout(() => setConfirmDel(false), 4000);
      return;
    }
    try {
      await deleteLesson.mutateAsync(lessonId);
      // Возвращаемся на страницу курса (берём id из урока).
      if (lesson) {
        navigate(`/builder/courses/${lesson.course_id}`, { replace: true });
      } else {
        navigate("/builder", { replace: true });
      }
    } catch {
      setConfirmDel(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10 text-sm text-slate-500">
        Загрузка урока…
      </div>
    );
  }
  if (isError || !lesson) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-10">
        <section className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-sm text-rose-800">
          {error ? extractErrorMessage(error) : "Урок не найден."}
        </section>
      </div>
    );
  }

  return (
    <LessonEditorShell
      heading={`Редактирование урока: ${lesson.title}`}
      subheading="Изменения сохраняются по кнопке «Сохранить»."
      backLink={`/builder/courses/${lesson.course_id}`}
      content={content}
      setContent={setContent}
      register={register}
      errors={errors}
      onSave={onSave}
      saving={updateLesson.isPending}
      saveError={updateLesson.isError ? extractErrorMessage(updateLesson.error) : null}
      saveSuccess={savedAt !== null && !updateLesson.isPending && !updateLesson.isError}
      savedAt={savedAt}
      onDelete={onDelete}
      deleting={deleteLesson.isPending}
      confirmDel={confirmDel}
      deleteError={deleteLesson.isError ? extractErrorMessage(deleteLesson.error) : null}
    />
  );
}


// =======================================================================
// Общий каркас: метаданные + редактор + превью
// =======================================================================

interface ShellProps {
  heading:      string;
  subheading:   string;
  backLink:     string | null;
  content:      string;
  setContent:   (v: string) => void;
  register:     UseFormRegister<FormFields>;
  errors:       FieldErrors<FormFields>;
  onSave:       () => void;
  saving:       boolean;
  saveError:    string | null;
  saveSuccess:  boolean;
  savedAt?:     Date | null;
  onDelete:     null | (() => void);
  deleting?:    boolean;
  confirmDel?:  boolean;
  deleteError?: string | null;
}

function LessonEditorShell(props: ShellProps) {
  const {
    heading, subheading, backLink, content, setContent,
    register, errors, onSave, saving, saveError, saveSuccess, savedAt,
    onDelete, deleting, confirmDel, deleteError,
  } = props;

  // На мобильном/узком экране — переключаемся между «код» и «превью» табами.
  const [mobileTab, setMobileTab] = useState<"edit" | "preview">("edit");

  // Простая статистика: символов и оценочное время чтения (180 слов/мин).
  const stats = useMemo(() => {
    const chars = content.length;
    const words = content.trim().split(/\s+/).filter(Boolean).length;
    const readMin = Math.max(1, Math.round(words / 180));
    return { chars, words, readMin };
  }, [content]);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">

      {backLink ? (
        <Link to={backLink} className="text-sm text-slate-500 hover:text-slate-900">
          ← К курсу
        </Link>
      ) : (
        <Link to="/builder" className="text-sm text-slate-500 hover:text-slate-900">
          ← К списку курсов
        </Link>
      )}

      <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">{heading}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{subheading}</p>
        </div>

        {/* Статус сохранения */}
        <div className="flex items-center gap-2 text-xs">
          {saving && (
            <span className="flex items-center gap-1.5 text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Сохранение…
            </span>
          )}
          {saveSuccess && savedAt && !saving && (
            <span className="text-emerald-700">
              ✓ Сохранено в {savedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
      </div>

      {saveError && (
        <div className="mt-4 bg-rose-50 border border-rose-200 rounded-lg p-3 flex items-start gap-2 text-sm text-rose-800">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{saveError}</span>
        </div>
      )}
      {deleteError && (
        <div className="mt-4 bg-rose-50 border border-rose-200 rounded-lg p-3 flex items-start gap-2 text-sm text-rose-800">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{deleteError}</span>
        </div>
      )}

      <form className="mt-6 grid grid-cols-1 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-5">

        {/* ===== Левая колонка: метаданные ===== */}
        <div className="space-y-4">

          <section className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500">
              Параметры урока
            </h2>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Название</label>
              <input
                type="text"
                placeholder="Например: Введение в MongoDB"
                {...register("title", {
                  required: "Введите название",
                  minLength: { value: 3,   message: "Минимум 3 символа"   },
                  maxLength: { value: 255, message: "Максимум 255 символов" },
                })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.title && (
                <p className="text-xs text-rose-600 mt-1">{errors.title.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Порядок</label>
                <input
                  type="number"
                  min={1}
                  {...register("order_num", { valueAsNumber: true, min: 1, required: true })}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded"
                />
                <p className="text-[11px] text-slate-500 mt-1">Внутри модуля</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Время, мин</label>
                <input
                  type="number"
                  min={1}
                  max={300}
                  placeholder="—"
                  {...register("duration_min", {
                    setValueAs: (v) => (v === "" || v == null ? null : Number(v)),
                    validate: (v) =>
                      v == null || (v >= 1 && v <= 300) || "От 1 до 300 минут",
                  })}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded"
                />
                <p className="text-[11px] text-slate-500 mt-1">Опционально</p>
              </div>
            </div>
            {errors.duration_min && (
              <p className="text-xs text-rose-600 -mt-2">{errors.duration_min.message}</p>
            )}
          </section>

          {/* Статистика */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Статистика
            </h2>
            <dl className="grid grid-cols-3 gap-2 text-center">
              <div>
                <dt className="text-[11px] text-slate-500 uppercase">Символов</dt>
                <dd className="text-lg font-semibold mt-0.5">{stats.chars}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500 uppercase">Слов</dt>
                <dd className="text-lg font-semibold mt-0.5">{stats.words}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500 uppercase">~ чтения</dt>
                <dd className="text-lg font-semibold mt-0.5">{stats.readMin} мин</dd>
              </div>
            </dl>
            {stats.chars > 18000 && (
              <p className="text-[11px] text-amber-700 mt-3">
                Близко к лимиту (20 000 символов).
              </p>
            )}
          </section>

          {/* Шпаргалка по Markdown */}
          <section className="bg-slate-50 rounded-lg border border-slate-200 p-5">
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Markdown — кратко
            </h2>
            <ul className="text-[12px] text-slate-700 space-y-1 font-mono">
              <li><code># Заголовок</code> — H1</li>
              <li><code>## Подзаголовок</code> — H2</li>
              <li><code>**жирный**</code>, <code>*курсив*</code></li>
              <li><code>- пункт</code> — список</li>
              <li><code>`код`</code> — инлайн-код</li>
              <li><code>```js</code> — блок кода</li>
              <li><code>[текст](url)</code> — ссылка</li>
              <li><code>&gt; цитата</code> — блок-цитата</li>
            </ul>
          </section>

          {/* Кнопки действий */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 rounded font-medium"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Сохранить
            </button>

            {onDelete && (
              <button
                type="button"
                onClick={onDelete}
                disabled={deleting}
                className={
                  "w-full flex items-center justify-center gap-2 px-4 py-2 text-xs rounded border font-medium " +
                  (confirmDel
                    ? "bg-rose-600 text-white border-rose-600 hover:bg-rose-700"
                    : "bg-white text-rose-600 border-rose-200 hover:bg-rose-50")
                }
              >
                {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                {confirmDel ? "Точно удалить? Нажмите ещё раз" : "Удалить урок"}
              </button>
            )}
          </div>
        </div>

        {/* ===== Правая колонка: редактор + превью ===== */}
        <div className="space-y-4">

          {/* Табы для мобилки */}
          <div className="lg:hidden flex bg-white rounded-lg border border-slate-200 p-1">
            <button
              type="button"
              onClick={() => setMobileTab("edit")}
              className={
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded " +
                (mobileTab === "edit" ? "bg-slate-100 text-slate-900" : "text-slate-500")
              }
            >
              <CodeIcon className="w-3.5 h-3.5" />
              Markdown
            </button>
            <button
              type="button"
              onClick={() => setMobileTab("preview")}
              className={
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded " +
                (mobileTab === "preview" ? "bg-slate-100 text-slate-900" : "text-slate-500")
              }
            >
              <Eye className="w-3.5 h-3.5" />
              Превью
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {/* Редактор Markdown */}
            <section
              className={
                "bg-white rounded-lg border border-slate-200 overflow-hidden flex flex-col " +
                (mobileTab === "preview" ? "hidden lg:flex" : "")
              }
              style={{ minHeight: "640px" }}
            >
              <header className="px-4 py-2 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CodeIcon className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Markdown
                  </span>
                </div>
                <span
                  className={
                    "text-[11px] font-mono " +
                    (stats.chars > 20000
                      ? "text-rose-600 font-semibold"
                      : stats.chars > 18000
                        ? "text-amber-700"
                        : "text-slate-400")
                  }
                  title={
                    stats.chars > 20000
                      ? "Превышен лимит — сохранение вернёт ошибку"
                      : "Лимит на содержимое урока — 20 000 символов"
                  }
                >
                  {stats.chars} / 20000
                </span>
              </header>
              <div className="flex-1">
                <Editor
                  height="640px"
                  defaultLanguage="markdown"
                  value={content}
                  onChange={(v) => setContent(v ?? "")}
                  options={{
                    minimap:        { enabled: false },
                    fontSize:       13,
                    wordWrap:       "on",
                    lineNumbers:    "on",
                    scrollBeyondLastLine: false,
                    padding:        { top: 8, bottom: 8 },
                  }}
                />
              </div>
            </section>

            {/* Превью */}
            <section
              className={
                "bg-white rounded-lg border border-slate-200 overflow-hidden flex flex-col " +
                (mobileTab === "edit" ? "hidden lg:flex" : "")
              }
              style={{ minHeight: "640px" }}
            >
              <header className="px-4 py-2 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Превью (как увидит студент)
                </span>
              </header>
              <div className="flex-1 overflow-y-auto p-6" style={{ maxHeight: "640px" }}>
                {content.trim() ? (
                  <div className="prose-lesson">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400 italic">Превью появится здесь.</p>
                )}
              </div>
            </section>

          </div>
        </div>

      </form>
    </div>
  );
}
