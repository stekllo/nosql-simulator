/**
 * Конструктор нового задания.
 *
 * Две колонки:
 *  - слева: формулировка, тип СУБД, баллы, лимит попыток, флаг compare_ordered
 *  - справа: редактор fixture, основной эталон, дополнительные эталоны (можно добавлять/удалять),
 *            кнопка «Проверить эталон» с preview результата.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import Editor from "@monaco-editor/react";
import { Play, Save, CheckCircle2, XCircle, Loader2, Plus, Trash2 } from "lucide-react";

import { useCreateTask, useReferenceDryRun } from "@/hooks/useBuilder";
import { extractErrorMessage } from "@/lib/api";
import type { NoSQLType, ReferenceDryRun, TaskCreate } from "@/lib/types";


interface FormFields {
  statement:       string;
  db_type:         NoSQLType;
  max_score:       number;
  attempts_limit:  number;
  compare_ordered: boolean;
}


// ---------- Стартеры под разные типы СУБД ----------
//
// При создании нового задания мы автоматически подставляем заглушки,
// чтобы препод видел правильный формат fixture / эталона. Когда препод
// меняет тип СУБД в селекторе — стартеры тоже меняются (если препод
// ещё не правил поля вручную).

const STARTER_FIXTURES: Record<"document" | "key_value", string> = {
  document: `{
  "collection": "orders",
  "documents": [
    { "_id": 1, "user_id": "u_001", "status": "paid",      "amount": 100 },
    { "_id": 2, "user_id": "u_001", "status": "paid",      "amount": 250 },
    { "_id": 3, "user_id": "u_002", "status": "cancelled", "amount": 80  }
  ]
}`,
  key_value: `{
  "preload": [
    "SET counter 10",
    "SET name Anna"
  ]
}`,
};

const STARTER_SOLUTIONS: Record<"document" | "key_value", string> = {
  document: `db.orders.aggregate([
  { $match: { status: "paid" } },
  { $group: { _id: "$user_id", total: { $sum: "$amount" } } },
  { $sort:  { total: -1 } }
])`,
  key_value: `# Каждая строка — отдельная команда.
# Возвращается результат последней.
INCR counter
GET counter`,
};

// Какой Monaco-язык подсветки использовать для редактора эталона.
const SOLUTION_LANGUAGE: Record<NoSQLType, string> = {
  document:  "javascript",
  key_value: "shell",
  column:    "sql",
  graph:     "plaintext",
  mixed:     "plaintext",
};

// Метка СУБД, которая отображается в шапке редактора.
const DB_LABEL: Record<NoSQLType, string> = {
  document:  "MongoDB",
  key_value: "Redis",
  column:    "Cassandra",
  graph:     "Neo4j",
  mixed:     "Mixed",
};


export function TaskBuilderPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const lessonIdNum  = Number(lessonId);
  const navigate     = useNavigate();

  const dryRun     = useReferenceDryRun();
  const createTask = useCreateTask(lessonIdNum);

  const [fixtureText,   setFixtureText]   = useState(STARTER_FIXTURES.document);
  const [solutionText,  setSolutionText]  = useState(STARTER_SOLUTIONS.document);
  // Дополнительные эталоны (могут быть пустыми или несколько штук).
  const [altSolutions,  setAltSolutions]  = useState<string[]>([]);
  const [fixtureError,  setFixtureError]  = useState<string | null>(null);

  const {
    register, handleSubmit, watch, formState: { errors },
  } = useForm<FormFields>({
    defaultValues: {
      statement:       "",
      db_type:         "document",
      max_score:       10,
      attempts_limit:  5,
      compare_ordered: true,
    },
  });

  // Текущий выбранный тип СУБД — нужен для подсветки и подсказок.
  const dbType = watch("db_type");

  // При смене типа СУБД заменяем стартеры в редакторах,
  // НО только если препод ещё не правил их вручную (защита от потери работы).
  // «Не правил» = текст совпадает с одним из известных стартеров.
  useEffect(() => {
    if (dbType !== "document" && dbType !== "key_value") return;

    const knownFixtures  = Object.values(STARTER_FIXTURES);
    const knownSolutions = Object.values(STARTER_SOLUTIONS);

    if (knownFixtures.includes(fixtureText)) {
      setFixtureText(STARTER_FIXTURES[dbType]);
    }
    if (knownSolutions.includes(solutionText)) {
      setSolutionText(STARTER_SOLUTIONS[dbType]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dbType]);

  /** Валидация JSON fixture. */
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

  const buildPayload = (fields: FormFields): TaskCreate | null => {
    const fixture = parseFixture();
    if (!fixture) return null;
    // Фильтруем пустые альтернативные эталоны.
    const refs = altSolutions.map(s => s.trim()).filter(s => s.length > 0);
    return {
      statement:           fields.statement,
      db_type:             fields.db_type,
      fixture,
      reference_solution:  solutionText,
      reference_solutions: refs.length > 0 ? [solutionText, ...refs] : [],
      compare_ordered:     fields.compare_ordered,
      max_score:           fields.max_score,
      attempts_limit:      fields.attempts_limit,
    };
  };

  const onDryRun = handleSubmit((fields) => {
    const payload = buildPayload(fields);
    if (payload) dryRun.mutate(payload);
  });

  const onSave = handleSubmit(async (fields) => {
    const payload = buildPayload(fields);
    if (!payload) return;
    try {
      const task = await createTask.mutateAsync(payload);
      navigate(`/tasks/${task.task_id}`);
    } catch {
      /* ошибка отобразится через createTask.error */
    }
  });

  const addAltSolution = () => {
    setAltSolutions([...altSolutions, ""]);
  };

  const updateAltSolution = (idx: number, value: string) => {
    const next = [...altSolutions];
    next[idx] = value;
    setAltSolutions(next);
  };

  const removeAltSolution = (idx: number) => {
    setAltSolutions(altSolutions.filter((_, i) => i !== idx));
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">

      <Link to={-1 as unknown as string} className="text-sm text-slate-500 hover:text-slate-900">
        ← Назад
      </Link>

      <h1 className="text-[22px] font-semibold tracking-tight mt-3">Новое задание</h1>
      <p className="text-sm text-slate-500 mt-0.5">
        Опишите условие, подготовьте исходные данные и эталонное решение.
      </p>

      <form className="mt-6 grid grid-cols-1 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] gap-5">

        {/* ===== Левая колонка: мета ===== */}
        <div className="space-y-4">

          <section className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500">Параметры</h2>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Формулировка задания</label>
              <textarea
                rows={6}
                placeholder="Например: Для каждого пользователя из коллекции `orders` посчитайте суммарную стоимость оплаченных заказов..."
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
              <select
                {...register("db_type")}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded bg-white"
              >
                <option value="document">MongoDB (document)</option>
                <option value="key_value">Redis (key-value)</option>
                <option value="column"    disabled>Cassandra (column) — скоро</option>
                <option value="graph"     disabled>Neo4j (graph) — скоро</option>
              </select>
              <p className="text-[11px] text-slate-500 mt-1">
                Автоматическая проверка работает для MongoDB и Redis. Cassandra и Neo4j — скоро.
              </p>
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

            {/* Флаг сравнения с учётом порядка */}
            <div className="border-t border-slate-100 pt-4">
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  {...register("compare_ordered")}
                  className="mt-0.5 w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <span className="text-sm font-medium text-slate-700">Учитывать порядок результата</span>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Включите, если в задании используется <code className="font-mono">$sort</code> или <code className="font-mono">$limit</code>.
                    Иначе порядок элементов в массиве не повлияет на результат сравнения.
                  </p>
                </div>
              </label>
            </div>
          </section>

          {/* Preview */}
          <PreviewPanel data={dryRun.data} isPending={dryRun.isPending} error={dryRun.error} />

        </div>

        {/* ===== Правая колонка: редакторы ===== */}
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

          {/* Кнопка "Добавить альтернативный эталон" */}
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

          {/* Actions */}
          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500 max-w-md">
              Перед сохранением рекомендуем нажать «Проверить эталон», чтобы убедиться, что решение отрабатывает корректно.
            </div>
            <div className="flex items-center gap-2">
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
              <button
                type="button"
                onClick={onSave}
                disabled={createTask.isPending}
                className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 rounded flex items-center gap-2 font-medium"
              >
                {createTask.isPending
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Save className="w-4 h-4" />}
                Сохранить задание
              </button>
            </div>
          </div>

          {createTask.isError && (
            <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">
              Не удалось сохранить: {extractErrorMessage(createTask.error)}
            </div>
          )}

        </div>

      </form>
    </div>
  );
}


// ============ Панель превью ============

function PreviewPanel({
  data, isPending, error,
}: {
  data:      ReferenceDryRun | undefined;
  isPending: boolean;
  error:     unknown;
}) {
  if (!data && !isPending && !error) {
    return (
      <section className="bg-slate-50 border border-dashed border-slate-300 rounded-lg p-5 text-xs text-slate-500">
        Нажмите «Проверить эталон», чтобы выполнить эталонное решение на исходных данных и убедиться, что оно отрабатывает без ошибок.
      </section>
    );
  }

  if (isPending) {
    return (
      <section className="bg-white rounded-lg border border-slate-200 p-5 text-xs text-slate-500">
        <Loader2 className="inline w-4 h-4 mr-2 animate-spin" />
        Запускаем эталон в песочнице…
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-sm text-rose-800">
        {extractErrorMessage(error)}
      </section>
    );
  }

  if (!data) return null;

  const ok     = data.ok;
  const Icon   = ok ? CheckCircle2 : XCircle;
  const bg     = ok ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200";
  const iconCl = ok ? "text-emerald-600"                  : "text-rose-600";
  const title  = ok ? "Эталон отработал"                  : "Эталон упал";

  return (
    <section className={`rounded-lg border ${bg} overflow-hidden`}>
      <div className="px-4 py-2.5 border-b border-white/50 flex items-center gap-2">
        <Icon className={`w-4 h-4 ${iconCl}`} />
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
        <span className="ml-auto text-xs text-slate-500">{data.duration_ms} мс</span>
      </div>
      {data.error && (
        <pre className="px-4 py-2 text-xs text-rose-800 whitespace-pre-wrap">{data.error}</pre>
      )}
      {data.result != null && (
        <pre className="px-4 py-3 text-[12px] font-mono text-slate-800 whitespace-pre-wrap max-h-56 overflow-y-auto bg-white/60">
          {JSON.stringify(data.result, null, 2)}
        </pre>
      )}
    </section>
  );
}
