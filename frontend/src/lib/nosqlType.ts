/** Отображаемые названия и цвета для типов NoSQL СУБД. */
import type { NoSQLType } from "@/lib/types";

export const nosqlTypeLabel: Record<NoSQLType, string> = {
  document:  "DOCUMENT",
  key_value: "KEY-VALUE",
  column:    "COLUMN",
  graph:     "GRAPH",
  mixed:     "MIXED",
};

/**
 * Полные классы Tailwind на каждую пару цвет+оттенок.
 * Не используем шаблонные строки вида `bg-${color}-50`, потому что
 * Tailwind 4 JIT не сможет их обнаружить в исходниках и класс не попадёт в bundle.
 */
export const nosqlTypeBadge: Record<NoSQLType, string> = {
  document:  "bg-green-50  text-green-700  border-green-200",
  key_value: "bg-rose-50   text-rose-700   border-rose-200",
  column:    "bg-purple-50 text-purple-700 border-purple-200",
  graph:     "bg-blue-50   text-blue-700   border-blue-200",
  mixed:     "bg-slate-50  text-slate-700  border-slate-200",
};
