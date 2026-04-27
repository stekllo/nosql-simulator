/**
 * Редактирование существующего задания (включая эталон).
 *
 * Маршрут: /builder/tasks/:taskId/edit
 *
 * Доступно только автору курса (или админу) — backend это проверяет.
 * В отличие от TaskBuilderPage (создание новых), здесь:
 *   - тип СУБД показывается read-only (менять нельзя — это структурное изменение);
 *   - после Save остаёмся на странице со статусом «✓ Сохранено в HH:MM»;
 *   - есть кнопка «Удалить задание» с двойным подтверждением.
 *
 * Layout — как в TaskBuilderPage (две колонки: мета слева, JSON+эталон справа).
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import Editor from "@monaco-editor/react";
import {
  Play, Save, CheckCircle2, XCircle, Loader2, Plus, Trash2, AlertCircle,
} from "lucide-react";

import {
  useDeleteTask, useReferenceDryRun, useTaskForEdit, useUpdateTask,
} from "@/hooks/useBuilder";
import { extractErrorMessage } from "@/lib/api";
import type {
  NoSQLType, ReferenceDryRun, TaskCreate, TaskUpdatePayload,
} from "@/lib/types";


interface FormFields {
  statement:       string;
  max_score:       number;
  attempts_limit:  number;
  compare_ordered: boolean;
}


// Какой Monaco-язык использовать для подсветки эталона / preload-команд.
const SOLUTION_LANGUAGE: Record<NoSQLType, string> = {
  document:  "javascript",
  key_value: "shell",
  column:    "sql",
  graph:     "plaintext",
  mixed:     "plaintext",
};

const DB_LABEL: Record<NoSQLType, string> = {
  document:  "MongoDB",
  key_value: "Redis",
  column:    "Cassandra",
  graph:     "Neo4j",
  mixed:     "Mixed",
};


export function TaskEditorPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const taskIdNum  = Number(taskId);
  const navigate   = useNavigate();

  const taskQuery    = useTaskForEdit(taskId);
  const updateTask   = useUpdateTask(taskIdNum);
  const deleteTask   = useDeleteTask();
  const dryRun       = useReferenceDryRun();

  // Тексты редакторов хранятся отдельно — не в react-hook-form.
  const [fixtureText,   setFixtureText]   = useState("");
  const [solutionText,  setSolutionText]  = useState("");
  const [altSolutions,  setAltSolutions]  = useState<string[]>([]);
  const [fixtureError,  setFixtureError]  = useState<string | null>(null);
  const [savedAt,       setSavedAt]       = useState<Date | null>(null);
  const [confirmDel,    setConfirmDel]    = useState(false);

  const {
    register, handleSubmit, reset, formState: { errors },
  } = useForm<FormFields>({
    defaultValues: {
      statement:       "",
      max_score:       10,
      attempts_limit:  0,
      compare_ordered: true,
    },
  });

  const task = taskQuery.data ?? null;
  const dbType: NoSQLType = task?.db_type ?? "document";

  // Когда задание загрузилось — заполняем форму его данными.
  useEffect(() => {
    if (task) {
      reset({
        statement:       task.statement,
        max_score:       task.max_score,
        attempts_limit:  task.attempts_limit,
        compare_ordered: task.compare_ordered,
      });
      // fixture хранится в БД как dict — pretty-print для удобного чтения.
      setFixtureText(JSON.stringify(task.fixture, null, 2));
      setSolutionText(task.reference_solution);
      // reference_solutions в БД хранится так: [primary, ...alts] (см. patch-10).
      // Берём всё кроме первого как «альтернативные».
      if (task.reference_solutions && task.reference_solutions.length > 1) {
        setAltSolutions(task.reference_solutions.slice(1));
      } else {
        setAltSolutions([]);
      }
    }
  }, [task, reset]);

  // ---------- Парсинг fixture ----------

  const parseFixture = (): Record<string, unknown> | null => {
    try {
      const parsed = JSON.parse(fixtureText);
      setFixtureError(null);
      return parsed;
    } catch (err) {
      setFixtureError(`Некорректный JSON: ${(err as Error).message}`);
      return null;
    }
  };

  // ---------- Pack: собираем payload для PATCH ----------

  const buildPayload = (fields: FormFields): TaskUpdatePayload | null => {
    const fixture = parseFixture();
    if (!fixture) return null;
    const refs = altSolutions.map(s => s.trim()).filter(s => s.length > 0);
    return {
      statement:           fields.statement,
      fixture,
      reference_solution:  solutionText,
      // Семантика как в TaskBuilderPage: если есть альтернативы —
      // сохраняем основное решение первым в списке reference_solutions.
      reference_solutions: refs.length > 0 ? [solutionText, ...refs] : [],
      compare_ordered:     fields.compare_ordered,
      max_score:           fields.max_score,
      attempts_limit:      fields.attempts_limit,
    };
  };

  // Для dry-run нужен TaskCreate-shape, не TaskUpdate.
  const buildDryRunPayload = (fields: FormFields): TaskCreate | null => {
    if (!task) return null;
    const fixture = parseFixture();
    if (!fixture) return null;
    const refs = altSolutions.map(s => s.trim()).filter(s => s.length > 0);
    return {
      statement:           fields.statement,
      db_type:             task.db_type,   // не меняется
      fixture,
      reference_solution:  solutionText,
      reference_solutions: refs.length > 0 ? [solutionText, ...refs] : [],
      compare_ordered:     fields.compare_ordered,
      max_score:           fields.max_score,
      attempts_limit:      fields.attempts_limit,
    };
  };

  // ---------- Обработчики ----------

  const onDryRun = handleSubmit((fields) => {
    const payload = buildDryRunPayload(fields);
    if (payload) dryRun.mutate(payload);
  });

  const onSave = handleSubmit(async (fields) => {
    const payload = buildPayload(fields);
    if (!payload) return;
    try {
      await updateTask.mutateAsync(payload);
      setSavedAt(new Date());
    } catch {
      /* ошибка отрисуется через updateTask.error */
    }
  });

  const onDelete = async () => {
    if (!confirmDel) {
      setConfirmDel(true);
      setTimeout(() => setConfirmDel(false), 4000);
      return;
    }
    if (!task) return;
    try {
      await deleteTask.mutateAsync(taskIdNum);
      // После удаления возвращаемся к курсу, чтобы препод видел дерево.
      // course_id напрямую не знаем — но lesson_id у нас есть, и есть
      // обходной путь: navigate на /builder, оттуда препод выберет курс.
      // Либо можно подгрузить lesson, чтобы узнать course_id, но это лишний запрос.
      navigate("/builder");
    } catch {
      setConfirmDel(false);
    }
  };

  const addAltSolution    = () => setAltSolutions([...altSolutions, ""]);
  const updateAltSolution = (idx: number, value: string) => {
    const next = [...altSolutions];
    next[idx] = value;
    setAltSolutions(next);
  };
  const removeAltSolution = (idx: number) => {
    setAltSolutions(altSolutions.filter((_, i) => i !== idx));
  };

  // ---------- Состояния загрузки ----------

  if (taskQuery.isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10 text-sm text-slate-500">
        Загрузка задания…
      </div>
    );
  }
  if (taskQuery.isError || !task) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-10">
        <section className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-sm text-rose-800">
          {taskQuery.error
            ? extractErrorMessage(taskQuery.error)
            : "Задание не найдено."}
        </section>
        <Link to="/builder" className="inline-block mt-4 text-sm text-blue-700 hover:text-blue-900">
          ← К списку курсов
        </Link>
      </div>
    );
  }

  const saving      = updateTask.isPending;
  const deleting    = deleteTask.isPending;
  const saveError   = updateTask.error   ? extractErrorMessage(updateTask.error)   : null;
  const deleteError = deleteTask.error   ? extractErrorMessage(deleteTask.error)   : null;
  const saveSuccess = savedAt !== null && !saving && !updateTask.error;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">

      <Link to="/builder" className="text-sm text-slate-500 hover:text-slate-900">
        ← К списку курсов
      </Link>

      <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider">
              Редактирование задания
            </span>
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-200 text-slate-700 font-mono">
              {DB_LABEL[dbType]}
            </span>
          </div>
          <h1 className="text-[22px] font-semibold tracking-tight mt-1">
            Задание #{task.task_id}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Изменения сохраняются по кнопке «Сохранить». Тип СУБД задания
            менять нельзя — для этого создайте новое задание.
          </p>
        </div>

        {/* Статус сохранения */}
        <div className="flex items-center gap-2 text-xs">
          {saving && (
            <span className="flex items-center gap-1.5 text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Сохранение…
            </span>
          )}
          {saveSuccess && savedAt && (
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

      <form className="mt-6 grid grid-cols-1 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] gap-5">

        {/* ===== Левая колонка: мета ===== */}
        <div className="space-y-4">

          <section className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500">
              Параметры
            </h2>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Формулировка</label>
              <textarea
                rows={6}
                {...register("statement", {
                  required: "Введите формулировку",
                  minLength: { value: 10, message: "Минимум 10 символов" },
                })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600 resize-none"
              />
              {errors.statement && (
                <p className="text-xs text-rose-600 mt-1">{errors.statement.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Тип СУБД</label>
              <div className="px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded text-slate-600 font-mono">
                {DB_LABEL[dbType]} ({dbType})
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Изменить нельзя — пересоздайте задание.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Баллы</label>
                <input
                  type="number"
                  {...register("max_score", { valueAsNumber: true, min: 1, max: 100 })}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Лимит попыток</label>
                <input
                  type="number"
                  {...register("attempts_limit", { valueAsNumber: true, min: 0, max: 100 })}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded"
                />
                <p className="text-[11px] text-slate-500 mt-1">0 — без ограничений</p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                id="compare_ordered"
                {...register("compare_ordered")}
                className="mt-0.5"
              />
              <label htmlFor="compare_ordered" className="text-xs text-slate-700">
                <span className="font-medium">Учитывать порядок результата</span>
                <span className="block text-[11px] text-slate-500 mt-0.5">
                  Включите, если в задании используется $sort или $limit. Иначе порядок
                  элементов в массиве не повлияет на результат сравнения.
                </span>
              </label>
            </div>
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
              {confirmDel ? "Точно удалить? Нажмите ещё раз" : "Удалить задание"}
            </button>
          </div>
        </div>

        {/* ===== Правая колонка: JSON и эталоны ===== */}
        <div className="space-y-4">

          {/* Fixture */}
          <section className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-4 py-2 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                Исходные данные (fixture)
              </span>
              <span className="text-[10px] text-slate-500 font-mono">JSON · {DB_LABEL[dbType]}</span>
            </div>
            <div className="h-60">
              <Editor
                language="json"
                theme="vs-dark"
                value={fixtureText}
                onChange={(v) => setFixtureText(v ?? "")}
                options={{
                  fontFamily:  "ui-monospace, 'JetBrains Mono', Consolas, monospace",
                  fontSize:    12.5,
                  minimap:     { enabled: false },
                  scrollBeyondLastLine: false,
                  padding:     { top: 10 },
                }}
              />
            </div>
            {fixtureError && (
              <div className="px-4 py-2 text-xs text-rose-700 bg-rose-50 border-t border-rose-200">
                {fixtureError}
              </div>
            )}
          </section>

          {/* Основное эталонное решение */}
          <section className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-4 py-2 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                Эталонное решение
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{DB_LABEL[dbType]}</span>
            </div>
            <div className="h-64">
              <Editor
                language={SOLUTION_LANGUAGE[dbType]}
                theme="vs-dark"
                value={solutionText}
                onChange={(v) => setSolutionText(v ?? "")}
                options={{
                  fontFamily:  "ui-monospace, 'JetBrains Mono', Consolas, monospace",
                  fontSize:    12.5,
                  minimap:     { enabled: false },
                  scrollBeyondLastLine: false,
                  padding:     { top: 10 },
                }}
              />
            </div>
          </section>

          {/* Альтернативные эталоны */}
          {altSolutions.map((alt, idx) => (
            <section key={idx} className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <div className="px-4 py-2 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                  Альтернативный эталон #{idx + 1}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">{DB_LABEL[dbType]}</span>
                <button
                  type="button"
                  onClick={() => removeAltSolution(idx)}
                  className="ml-auto p-1 text-slate-500 hover:text-rose-600"
                  title="Удалить эталон"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="h-48">
                <Editor
                  language={SOLUTION_LANGUAGE[dbType]}
                  theme="vs-dark"
                  value={alt}
                  onChange={(v) => updateAltSolution(idx, v ?? "")}
                  options={{
                    fontFamily:  "ui-monospace, 'JetBrains Mono', Consolas, monospace",
                    fontSize:    12.5,
                    minimap:     { enabled: false },
                    scrollBeyondLastLine: false,
                    padding:     { top: 10 },
                  }}
                />
              </div>
            </section>
          ))}

          <button
            type="button"
            onClick={addAltSolution}
            className="w-full px-3 py-2 text-sm text-slate-600 bg-white border border-dashed border-slate-300 hover:bg-slate-50 hover:border-slate-400 rounded flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Добавить альтернативный эталон
          </button>
          <p className="text-[11px] text-slate-500 -mt-2">
            Если у задачи есть несколько правильных решений, добавьте каждый вариант. Студент пройдёт задание, если его ответ совпадёт хотя бы с одним из эталонов.
          </p>

          {/* Dry-run */}
          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500 max-w-md">
              Перед сохранением рекомендуем нажать «Проверить эталон», чтобы убедиться, что решение отрабатывает корректно.
            </div>
            <button
              type="button"
              onClick={onDryRun}
              disabled={dryRun.isPending}
              className="px-3.5 py-2 text-sm text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-60 rounded flex items-center gap-2"
            >
              {dryRun.isPending
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Play className="w-4 h-4" />}
              Проверить эталон
            </button>
          </div>

          {/* Результат dry-run */}
          {dryRun.data && (
            <DryRunResult result={dryRun.data} />
          )}
          {!!dryRun.error && (
            <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 flex items-start gap-2 text-sm text-rose-800">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{extractErrorMessage(dryRun.error)}</span>
            </div>
          )}

        </div>
      </form>

    </div>
  );
}


// ---------- Вспомогательный компонент: красивое отображение результата dry-run ----------

function DryRunResult({ result }: { result: ReferenceDryRun }) {
  if (result.ok) {
    return (
      <section className="bg-emerald-50 border border-emerald-200 rounded-lg overflow-hidden">
        <header className="px-4 py-2 border-b border-emerald-100 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-700" />
          <span className="text-xs font-medium uppercase tracking-wider text-emerald-700">
            Эталон отработал
          </span>
          <span className="ml-auto text-xs text-emerald-700">{result.duration_ms} мс</span>
        </header>
        <pre className="px-4 py-3 text-[12px] text-slate-900 whitespace-pre-wrap font-mono overflow-auto max-h-64">
          {JSON.stringify(result.result, null, 2)}
        </pre>
      </section>
    );
  }
  return (
    <section className="bg-rose-50 border border-rose-200 rounded-lg overflow-hidden">
      <header className="px-4 py-2 border-b border-rose-100 flex items-center gap-2">
        <XCircle className="w-4 h-4 text-rose-700" />
        <span className="text-xs font-medium uppercase tracking-wider text-rose-700">
          Эталон упал
        </span>
        <span className="ml-auto text-xs text-rose-700">{result.duration_ms} мс</span>
      </header>
      <pre className="px-4 py-3 text-[12px] text-rose-900 whitespace-pre-wrap font-mono">
        {result.error}
      </pre>
    </section>
  );
}
