/**
 * Страница выполнения задания: теория слева, редактор + результат справа.
 * Повторяет дизайн макета Рис. 2.6 из ВКР.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Play, RotateCcw, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import Editor, { OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useLessonByTask, useRunQuery, useSubmitQuery } from "@/hooks/useTask";
import { extractErrorMessage } from "@/lib/api";
import type { NoSQLType, RunResponse, SubmitResponse } from "@/lib/types";


// Стартовый код в редакторе зависит от типа БД задания.
const STARTER_QUERIES: Record<NoSQLType, string> = {
  document: `// Напишите здесь ваш запрос.
// Подсказка для aggregation: $match → $group → $sort → $limit.
db.orders.find({})
`,
  key_value: `# Напишите здесь Redis-команды (по одной на строку).
# Каждая строка — отдельная команда. Возвращается результат последней.
GET key
`,
  column: "-- CQL запрос (Cassandra)\nSELECT * FROM table;\n",
  graph:  "// Cypher запрос (Neo4j)\nMATCH (n) RETURN n LIMIT 10\n",
  mixed:  "",
};

// Какой Monaco-язык использовать для подсветки.
const LANGUAGE_BY_TYPE: Record<NoSQLType, string> = {
  document:  "javascript",   // MQL похож на JS-объекты
  key_value: "shell",        // Redis-команды визуально как shell
  column:    "sql",          // CQL — расширение SQL
  graph:     "cypher",       // Monaco не знает cypher из коробки → fallback на text
  mixed:     "plaintext",
};

// Человеко-читаемая метка БД для бейджа в редакторе.
const DB_BADGE_LABEL: Record<NoSQLType, string> = {
  document:  "MongoDB",
  key_value: "Redis",
  column:    "Cassandra",
  graph:     "Neo4j",
  mixed:     "Mixed",
};


export function TaskPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const taskIdNum  = Number(taskId);

  const { data: lesson, isLoading: lessonLoading } = useLessonByTask(taskId);
  const run    = useRunQuery(taskIdNum);
  const submit = useSubmitQuery(taskIdNum);

  // Находим именно то задание, которое открыто.
  const task = useMemo(
    () => lesson?.tasks.find((t) => t.task_id === taskIdNum) ?? null,
    [lesson, taskIdNum],
  );

  // Стартовый код подбирается под тип БД (Mongo / Redis / ...).
  const starterQuery = task ? STARTER_QUERIES[task.db_type] : STARTER_QUERIES.document;
  const editorLanguage = task ? LANGUAGE_BY_TYPE[task.db_type] : "javascript";
  const dbBadge = task ? DB_BADGE_LABEL[task.db_type] : "MongoDB";

  const [query, setQuery] = useState("");

  // Когда задание загрузилось — подставляем стартовый код для его типа.
  useEffect(() => {
    if (task && query === "") {
      setQuery(starterQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

  const handleEditorMount: OnMount = (ed, monaco) => {
    // Ctrl+Enter → запуск (dry run).
    ed.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      () => {
        const text = ed.getValue();
        run.mutate({ query_text: text });
      },
    );
  };

  const onRun    = () => run.mutate({ query_text: query });
  const onSubmit = () => submit.mutate({ query_text: query });
  const onReset  = () => {
    setQuery(starterQuery);
    run.reset();
    submit.reset();
  };

  if (lessonLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка…</div>;
  }
  if (!lesson || !task) {
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">Задание не найдено.</div>;
  }

  // Приоритет: результат submit > результат run.
  const latest: RunResponse | SubmitResponse | null = submit.data ?? run.data ?? null;
  const isSubmit = submit.data != null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]" style={{ height: "calc(100vh - 56px)" }}>

      {/* ===== LEFT: теория ===== */}
      <section className="bg-white border-r border-slate-200 overflow-y-auto p-7">
        <Link to={`/lessons/${lesson.lesson_id}`}
              className="text-sm text-slate-500 hover:text-slate-900">
          ← К уроку
        </Link>

        <h1 className="text-[22px] font-semibold tracking-tight mt-3">{lesson.title}</h1>

        <div className="prose-lesson mt-5">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{lesson.content_md}</ReactMarkdown>
        </div>
      </section>

      {/* ===== RIGHT: условие + редактор + результат ===== */}
      <section className="flex flex-col min-h-0 bg-slate-50">

        {/* Условие задания */}
        <div className="bg-white border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-2 text-xs text-slate-500 mb-1.5">
            <span className="font-medium uppercase tracking-wide">
              Задание
            </span>
            <span>•</span>
            <span>{task.max_score} баллов</span>
          </div>
          <p className="text-sm text-slate-900 leading-relaxed">{task.statement}</p>
        </div>

        {/* Редактор */}
        <div className="flex-1 min-h-0 bg-[#1e293b] flex flex-col">
          <div className="flex items-center justify-between border-b border-slate-700 px-4 py-2">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] text-slate-400 uppercase tracking-wider">
                {task?.db_type === "key_value" ? "query.redis" : "query.js"}
              </span>
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700 text-slate-300 font-mono">
                {dbBadge}
              </span>
            </div>
            <div className="font-mono text-xs text-slate-500">Ctrl + Enter — запуск</div>
          </div>

          <div className="flex-1 min-h-0">
            <Editor
              language={editorLanguage}
              theme="vs-dark"
              value={query}
              onChange={(v) => setQuery(v ?? "")}
              onMount={handleEditorMount}
              options={{
                fontFamily:           "ui-monospace, 'JetBrains Mono', Consolas, monospace",
                fontSize:             13,
                minimap:              { enabled: false },
                lineNumbersMinChars:  3,
                scrollBeyondLastLine: false,
                wordWrap:             "on",
                padding:              { top: 12 },
              }}
            />
          </div>

          {/* Action bar */}
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-700 bg-slate-900">
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Sandbox готова
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onReset}
                className="px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 rounded flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Сбросить
              </button>
              <button
                onClick={onRun}
                disabled={run.isPending}
                className="px-3 py-1.5 text-xs text-slate-200 bg-slate-700 hover:bg-slate-600 disabled:opacity-60 rounded flex items-center gap-1.5"
              >
                {run.isPending
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Play className="w-3.5 h-3.5" />}
                Запустить
              </button>
              <button
                onClick={onSubmit}
                disabled={submit.isPending}
                className="px-3.5 py-1.5 text-xs text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 rounded font-medium"
              >
                {submit.isPending ? "Отправка…" : "Отправить"}
              </button>
            </div>
          </div>
        </div>

        {/* Результат */}
        <ResultPanel
          latest={latest}
          isSubmit={isSubmit}
          isPending={run.isPending || submit.isPending}
          error={extractErrorMessage(run.error ?? submit.error) || null}
        />

      </section>
    </div>
  );
}


// ============ Панель результата ============

interface ResultPanelProps {
  latest:    RunResponse | SubmitResponse | null;
  isSubmit:  boolean;
  isPending: boolean;
  error:     string | null;
}

function ResultPanel({ latest, isSubmit, isPending, error }: ResultPanelProps) {
  if (isPending) {
    return (
      <div className="bg-white border-t border-slate-200 px-5 py-3 text-sm text-slate-500">
        <Loader2 className="inline w-4 h-4 mr-2 animate-spin" />
        Выполняется…
      </div>
    );
  }

  if (error && !latest) {
    return (
      <div className="bg-rose-50 border-t border-rose-200 px-5 py-3 text-sm text-rose-800">
        {error}
      </div>
    );
  }

  if (!latest) {
    return (
      <div className="bg-white border-t border-slate-200 px-5 py-3 text-xs text-slate-400">
        Нажмите «Запустить», чтобы выполнить запрос, или «Отправить», чтобы проверить решение.
      </div>
    );
  }

  // ошибка выполнения (только для run, не для submit — у RunResponse есть .ok)
  if (!isSubmit && "ok" in latest && !latest.ok) {
    return (
      <div className="bg-white border-t border-slate-200 max-h-64 overflow-y-auto">
        <div className="px-5 py-2.5 border-b border-slate-200 bg-rose-50 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-600" />
          <span className="text-xs font-medium uppercase tracking-wider text-rose-700">Ошибка</span>
          <span className="ml-auto text-xs text-slate-500">{latest.duration_ms} мс</span>
        </div>
        <pre className="px-5 py-3 text-[13px] text-slate-900 whitespace-pre-wrap">{latest.error}</pre>
      </div>
    );
  }

  // сабмит: правильно/неправильно/timeout
  if (isSubmit) {
    const sub = latest as SubmitResponse;

    const palette = {
      correct: { bg: "bg-emerald-50", text: "text-emerald-700", iconCls: "text-emerald-600", label: "Правильно",         Icon: CheckCircle2 },
      timeout: { bg: "bg-amber-50",   text: "text-amber-700",   iconCls: "text-amber-600",   label: "Превышен таймаут",  Icon: XCircle      },
      wrong:   { bg: "bg-rose-50",    text: "text-rose-700",    iconCls: "text-rose-600",    label: "Неверный ответ",    Icon: XCircle      },
      pending: { bg: "bg-slate-50",   text: "text-slate-700",   iconCls: "text-slate-600",   label: "Отправлено",        Icon: CheckCircle2 },
    } as const;

    const p = palette[sub.status] ?? palette.pending;
    const StatusIcon = p.Icon;

    return (
      <div className="bg-white border-t border-slate-200 max-h-80 overflow-y-auto">
        <div className={`px-5 py-2.5 border-b border-slate-200 ${p.bg} flex items-center gap-3`}>
          <StatusIcon className={`w-4 h-4 ${p.iconCls}`} />
          <span className={`text-xs font-medium uppercase tracking-wider ${p.text}`}>
            {p.label}
          </span>
          <span className="text-xs text-slate-500 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {sub.duration_ms} мс
          </span>
          <span className="ml-auto text-xs text-slate-500">
            Баллы: <b className={`${p.text} font-semibold`}>{sub.score ?? 0}</b>
          </span>
        </div>
        {sub.error && (
          <pre className="px-5 py-2 text-[13px] text-rose-800 bg-rose-50 whitespace-pre-wrap">{sub.error}</pre>
        )}
        <pre className="px-5 py-3 text-[13px] font-mono text-slate-800 whitespace-pre-wrap">
          {JSON.stringify(sub.result, null, 2)}
        </pre>
      </div>
    );
  }

  // dry run: просто показать результат
  const items = Array.isArray(latest.result) ? latest.result : null;
  return (
    <div className="bg-white border-t border-slate-200 max-h-64 overflow-y-auto">
      <div className="px-5 py-2.5 border-b border-slate-200 bg-slate-50 flex items-center gap-3">
        <CheckCircle2 className="w-4 h-4 text-slate-500" />
        <span className="text-xs font-medium uppercase tracking-wider text-slate-700">Результат</span>
        <span className="text-xs text-slate-500 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {latest.duration_ms} мс
        </span>
        {items && (
          <span className="ml-auto text-xs text-slate-500">{items.length} документов</span>
        )}
      </div>
      <pre className="px-5 py-3 text-[13px] font-mono text-slate-800 whitespace-pre-wrap">
        {JSON.stringify(latest.result, null, 2)}
      </pre>
    </div>
  );
}
