/**
 * Иконки СУБД для карточек курсов.
 *
 * Упрощённые inline SVG-логотипы NoSQL-СУБД в фирменных цветах.
 * Реализованы без зависимостей — чтобы не добавлять новых пакетов в package.json.
 */
import { Database } from "lucide-react";
import type { NoSQLType } from "@/lib/types";


type IconProps = {
  size?: number;
  className?: string;
};

/** MongoDB — зелёный лист (#00684A). */
function MongoDBIcon({ size = 24, className = "" }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
    >
      <path
        fill="#00684A"
        d="M12 2 C 12 2, 6 6, 6 13 C 6 18, 9 21, 11 22 L 11 23 L 13 23 L 13 22 C 15 21, 18 18, 18 13 C 18 6, 12 2, 12 2 Z M 12 5 C 12 5, 16 9, 15 14 C 15 17, 13 19, 12 20 L 12 5 Z"
      />
    </svg>
  );
}

/** Redis — стек дисков данных (красный, #DC382D). */
function RedisIcon({ size = 24, className = "" }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
    >
      <ellipse cx="12" cy="6" rx="9" ry="3" fill="#DC382D" />
      <path
        fill="#DC382D"
        d="M3 6 L 3 10 C 3 11.65, 7.03 13, 12 13 C 16.97 13, 21 11.65, 21 10 L 21 6 C 21 7.65, 16.97 9, 12 9 C 7.03 9, 3 7.65, 3 6 Z"
      />
      <path
        fill="#DC382D"
        d="M3 11 L 3 15 C 3 16.65, 7.03 18, 12 18 C 16.97 18, 21 16.65, 21 15 L 21 11 C 21 12.65, 16.97 14, 12 14 C 7.03 14, 3 12.65, 3 11 Z"
      />
      <path
        fill="#DC382D"
        d="M3 16 L 3 20 C 3 21.65, 7.03 23, 12 23 C 16.97 23, 21 21.65, 21 20 L 21 16 C 21 17.65, 16.97 19, 12 19 C 7.03 19, 3 17.65, 3 16 Z"
      />
    </svg>
  );
}

/** Cassandra — стилизованный глаз (голубой, #1287B1). */
function CassandraIcon({ size = 24, className = "" }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" fill="none" stroke="#1287B1" strokeWidth="2" />
      <circle cx="12" cy="12" r="3" fill="#1287B1" />
      <path
        d="M2 12 Q 12 4, 22 12 Q 12 20, 2 12 Z"
        fill="none"
        stroke="#1287B1"
        strokeWidth="1.5"
      />
    </svg>
  );
}

/** Neo4j — узлы графа с рёбрами (синий, #018BFF). */
function Neo4jIcon({ size = 24, className = "" }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
    >
      <g fill="#018BFF" stroke="#018BFF" strokeWidth="1.4" strokeLinecap="round">
        <line x1="6" y1="6" x2="12" y2="12" />
        <line x1="18" y1="6" x2="12" y2="12" />
        <line x1="12" y1="12" x2="6" y2="18" />
        <line x1="12" y1="12" x2="18" y2="18" />
        <circle cx="6" cy="6" r="2.2" />
        <circle cx="18" cy="6" r="2.2" />
        <circle cx="12" cy="12" r="2.7" />
        <circle cx="6" cy="18" r="2.2" />
        <circle cx="18" cy="18" r="2.2" />
      </g>
    </svg>
  );
}


/**
 * Возвращает иконку для данного типа NoSQL-СУБД.
 *
 * Для типа MIXED — generic-иконка из lucide-react.
 *
 * Использование:
 *   <NoSQLIcon type="document" size={28} />
 */
export function NoSQLIcon({
  type,
  size = 24,
  className = "",
}: {
  type: NoSQLType;
  size?: number;
  className?: string;
}) {
  switch (type) {
    case "document":
      return <MongoDBIcon size={size} className={className} />;
    case "key_value":
      return <RedisIcon size={size} className={className} />;
    case "column":
      return <CassandraIcon size={size} className={className} />;
    case "graph":
      return <Neo4jIcon size={size} className={className} />;
    case "mixed":
    default:
      return <Database size={size} className={className} color="#475569" />;
  }
}
