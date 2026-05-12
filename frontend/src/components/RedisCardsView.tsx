/**
 * Карточки ключ-значение для результатов Redis.
 *
 * Redis-runner может возвращать разные форматы — простые значения,
 * массивы, словари из HGETALL, упорядоченные множества. Мы пытаемся
 * угадать тип значения и подсвечиваем его цветным бейджем.
 */

const TYPE_COLOR: Record<string, string> = {
  STRING:  "bg-red-600",
  LIST:    "bg-blue-600",
  HASH:    "bg-orange-500",
  SET:     "bg-green-600",
  ZSET:    "bg-purple-600",
  INTEGER: "bg-slate-600",
  NIL:     "bg-slate-400",
};


export function RedisCardsView({ data }: { data: unknown }) {
  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <Empty />;
    }

    const allScalars = data.every(item => typeof item !== "object" || item === null);
    if (allScalars) {
      return (
        <div className="space-y-2">
          {data.map((v, i) => (
            <SimpleCard key={i} value={v} />
          ))}
        </div>
      );
    }

    return (
      <div className="space-y-2">
        {data.map((item, i) => (
          <RedisCard key={i} item={item} />
        ))}
      </div>
    );
  }

  return <SimpleCard value={data} />;
}


function RedisCard({ item }: { item: unknown }) {
  if (item === null || typeof item !== "object") {
    return <SimpleCard value={item} />;
  }
  const obj = item as Record<string, unknown>;

  if ("key" in obj && "value" in obj) {
    const type = detectType(obj.value);
    const ttl  = "ttl" in obj && typeof obj.ttl === "number" ? obj.ttl : null;
    return (
      <div className="bg-white border border-rose-100 rounded-lg px-3.5 py-2.5">
        <div className="flex items-center gap-2.5 mb-1.5">
          <TypeBadge type={type} />
          <span className="font-mono text-sm font-semibold text-slate-800">
            {String(obj.key)}
          </span>
          {ttl !== null && (
            <span className="ml-auto text-[11px] text-slate-500">TTL: {ttl}s</span>
          )}
        </div>
        <FormattedValue value={obj.value} />
      </div>
    );
  }

  return (
    <div className="bg-white border border-rose-100 rounded-lg px-3.5 py-2.5">
      <div className="flex items-center gap-2.5 mb-1.5">
        <TypeBadge type="HASH" />
      </div>
      <FormattedValue value={obj} />
    </div>
  );
}


function SimpleCard({ value }: { value: unknown }) {
  return (
    <div className="bg-white border border-rose-100 rounded-lg px-3.5 py-2.5">
      <div className="flex items-center gap-2.5 mb-1.5">
        <TypeBadge type={detectType(value)} />
      </div>
      <FormattedValue value={value} />
    </div>
  );
}


function detectType(v: unknown): string {
  if (v === null || v === undefined)  return "NIL";
  if (typeof v === "string")          return "STRING";
  if (typeof v === "number")          return "INTEGER";
  if (Array.isArray(v))               return "LIST";
  if (typeof v === "object")          return "HASH";
  return "STRING";
}

function TypeBadge({ type }: { type: string }) {
  const color = TYPE_COLOR[type] ?? "bg-slate-500";
  return (
    <span className={`${color} text-white text-[10px] px-2 py-0.5 rounded font-semibold tracking-wide`}>
      {type}
    </span>
  );
}

function FormattedValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="font-mono text-[12.5px] text-slate-400 italic">(nil)</span>;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return (
      <code className="font-mono text-[12.5px] text-slate-700">
        {typeof value === "string" ? `"${value}"` : String(value)}
      </code>
    );
  }
  return (
    <code className="font-mono text-[12.5px] text-slate-700 break-all">
      {JSON.stringify(value)}
    </code>
  );
}

function Empty() {
  return (
    <div className="text-sm text-slate-500 italic px-1 py-2">
      Запрос не вернул значений.
    </div>
  );
}
