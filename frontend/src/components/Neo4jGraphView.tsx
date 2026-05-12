/**
 * SVG-рендер графа для результатов Neo4j.
 *
 * Распознаёт узлы и связи в результате запроса по структуре объектов
 * (формат, который возвращает наш Neo4j-runner):
 *
 *   узел  -> { labels: [...], properties: {...} }
 *   связь -> { type: "...",   properties: {...} }
 *
 * Поскольку связи в нашем формате не содержат ссылок на конкретные
 * узлы (нет start_node_id / end_node_id), мы используем эвристику:
 * связь в записи `{a, r, b}` соединяет узел `a` с узлом `b`. Это
 * работает для типичных Cypher-запросов вида `MATCH (a)-[r]->(b)`.
 *
 * Расположение узлов — по кластерам: узлы каждой метки группируются
 * в вертикальный столбец, столбцы выстраиваются слева направо.
 */


// ───────── публичный API ─────────

interface Props {
  data: unknown;
}

export function Neo4jGraphView({ data }: Props) {
  const graph = extractGraph(data);

  if (graph.nodes.length === 0) {
    return (
      <div className="text-sm text-slate-500 italic px-1 py-4">
        Запрос не вернул узлов. Используйте вкладку «Просмотр» или «JSON».
      </div>
    );
  }

  return <GraphSVG graph={graph} />;
}


// ───────── распознавание узлов и связей в JSON ─────────

interface RawNode {
  /** Подпись для отображения — обычно properties.name */
  caption: string;
  /** Стабильный идентификатор узла (по labels + properties) */
  id:      string;
  /** Метки Neo4j: [":Person"] */
  labels:  string[];
  /** Сырое содержимое properties для тултипа (зарезервировано) */
  props:   Record<string, unknown>;
}

interface RawEdge {
  type:       string;
  sourceId:   string;
  targetId:   string;
}

interface Graph {
  nodes: RawNode[];
  edges: RawEdge[];
}


/** Проверяет, выглядит ли значение как Neo4j-узел из нашего runner-а. */
function isNode(v: unknown): v is { labels: string[]; properties: Record<string, unknown> } {
  if (v === null || typeof v !== "object") return false;
  const obj = v as Record<string, unknown>;
  return Array.isArray(obj.labels)
      && obj.labels.every(l => typeof l === "string")
      && typeof obj.properties === "object"
      && obj.properties !== null;
}

/** Проверяет, выглядит ли значение как Neo4j-связь из нашего runner-а. */
function isEdge(v: unknown): v is { type: string; properties: Record<string, unknown> } {
  if (v === null || typeof v !== "object") return false;
  const obj = v as Record<string, unknown>;
  return typeof obj.type === "string"
      && typeof obj.properties === "object"
      && obj.properties !== null
      && !Array.isArray((obj as { labels?: unknown }).labels);  // ← отличаем от узла
}


/** Стабильный отпечаток узла для дедупликации. */
function nodeId(n: { labels: string[]; properties: Record<string, unknown> }): string {
  // Стабильная сериализация properties
  const sortedProps = Object.keys(n.properties)
    .sort()
    .map(k => `${k}:${JSON.stringify(n.properties[k])}`)
    .join(",");
  return `[${n.labels.join(",")}]{${sortedProps}}`;
}


/** Извлекает текст подписи из properties (приоритет: name → title → первое строковое поле). */
function nodeCaption(props: Record<string, unknown>): string {
  if (typeof props.name === "string")  return props.name;
  if (typeof props.title === "string") return props.title;
  // Берём первое строковое свойство
  for (const v of Object.values(props)) {
    if (typeof v === "string") return v;
  }
  // Иначе — первое значение или плейсхолдер
  for (const v of Object.values(props)) {
    return String(v);
  }
  return "?";
}


/** Парсит произвольный JSON и собирает граф (узлы + связи). */
function extractGraph(data: unknown): Graph {
  const nodes = new Map<string, RawNode>();
  const edges: RawEdge[] = [];

  if (!Array.isArray(data)) return { nodes: [], edges };

  for (const record of data) {
    if (record === null || typeof record !== "object") continue;
    const fields = record as Record<string, unknown>;

    // Сначала собираем все узлы из этой записи и порядок их появления.
    const orderedKeys = Object.keys(fields);
    const recordNodes: { key: string; id: string }[] = [];

    for (const key of orderedKeys) {
      const v = fields[key];
      if (isNode(v)) {
        const id = nodeId(v);
        if (!nodes.has(id)) {
          nodes.set(id, {
            id,
            caption: nodeCaption(v.properties),
            labels:  v.labels,
            props:   v.properties,
          });
        }
        recordNodes.push({ key, id });
      }
    }

    // Затем для каждой связи находим ближайшие узлы слева и справа от неё.
    for (let i = 0; i < orderedKeys.length; i++) {
      const v = fields[orderedKeys[i]];
      if (!isEdge(v)) continue;

      // Ищем узел, появившийся последним перед этой связью.
      const before = lastNodeBefore(orderedKeys, i, fields);
      // Ищем первый узел, появившийся после этой связи.
      const after  = firstNodeAfter(orderedKeys, i, fields);

      if (before && after) {
        edges.push({ type: v.type, sourceId: before, targetId: after });
      }
    }
  }

  return { nodes: Array.from(nodes.values()), edges };
}


function lastNodeBefore(keys: string[], idx: number, fields: Record<string, unknown>): string | null {
  for (let i = idx - 1; i >= 0; i--) {
    const v = fields[keys[i]];
    if (isNode(v)) return nodeId(v);
  }
  return null;
}

function firstNodeAfter(keys: string[], idx: number, fields: Record<string, unknown>): string | null {
  for (let i = idx + 1; i < keys.length; i++) {
    const v = fields[keys[i]];
    if (isNode(v)) return nodeId(v);
  }
  return null;
}


// ───────── позиционирование узлов и SVG-рендер ─────────

/** Цвета для меток. Первая встретившаяся метка получает фирменный цвет. */
const LABEL_PALETTE: { fill: string; stroke: string; text: string }[] = [
  { fill: "#fbbf24", stroke: "#d97706", text: "#78350f" }, // золотистый
  { fill: "#7dd3fc", stroke: "#0284c7", text: "#0c4a6e" }, // голубой
  { fill: "#86efac", stroke: "#16a34a", text: "#14532d" }, // зелёный
  { fill: "#f9a8d4", stroke: "#db2777", text: "#831843" }, // розовый
  { fill: "#c4b5fd", stroke: "#7c3aed", text: "#3b0764" }, // фиолетовый
  { fill: "#fda4af", stroke: "#e11d48", text: "#881337" }, // красный
];


function GraphSVG({ graph }: { graph: Graph }) {
  // Группируем узлы по «основной» метке (первой в массиве).
  const groups = new Map<string, RawNode[]>();
  for (const n of graph.nodes) {
    const lbl = n.labels[0] ?? "Unknown";
    if (!groups.has(lbl)) groups.set(lbl, []);
    groups.get(lbl)!.push(n);
  }
  const labels = Array.from(groups.keys());

  // Цвет для каждой метки.
  const colorByLabel = new Map<string, typeof LABEL_PALETTE[0]>();
  labels.forEach((l, i) => colorByLabel.set(l, LABEL_PALETTE[i % LABEL_PALETTE.length]));

  // Раскладка: каждая метка — отдельный столбец слева направо.
  const VIEW_W = 700;
  const PAD_X  = 80;
  const PAD_Y  = 60;
  const COL_W  = (VIEW_W - PAD_X * 2) / Math.max(1, labels.length - 1 || 1);
  const NODE_R = 32;

  // Вычисляем максимальную высоту по самой большой группе.
  const maxRows = Math.max(...labels.map(l => groups.get(l)!.length));
  const ROW_H   = 90;
  const VIEW_H  = Math.max(220, PAD_Y * 2 + (maxRows - 1) * ROW_H + 40);

  // Координаты узлов.
  const pos = new Map<string, { x: number; y: number }>();
  labels.forEach((lbl, colIdx) => {
    const nodes = groups.get(lbl)!;
    const x = labels.length === 1 ? VIEW_W / 2 : PAD_X + colIdx * COL_W;
    const startY = PAD_Y + (maxRows - nodes.length) * (ROW_H / 2);
    nodes.forEach((n, rowIdx) => {
      pos.set(n.id, { x, y: startY + rowIdx * ROW_H });
    });
  });

  // ───────── рендер ─────────

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full h-auto block"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <marker id="nv-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Связи */}
        <g>
          {graph.edges.map((e, i) => {
            const s = pos.get(e.sourceId);
            const t = pos.get(e.targetId);
            if (!s || !t) return null;
            // Чтобы стрелка не упиралась в узел, чуть отодвигаем конец.
            const { x2, y2 } = trimToCircle(s, t, NODE_R);
            const midX = (s.x + x2) / 2;
            const midY = (s.y + y2) / 2;
            return (
              <g key={i}>
                <line
                  x1={s.x}
                  y1={s.y}
                  x2={x2}
                  y2={y2}
                  stroke="#94a3b8"
                  strokeWidth={1.5}
                  markerEnd="url(#nv-arrow)"
                />
                <text
                  x={midX}
                  y={midY - 5}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#64748b"
                  fontFamily="ui-sans-serif, system-ui, sans-serif"
                >
                  :{e.type}
                </text>
              </g>
            );
          })}
        </g>

        {/* Узлы */}
        <g>
          {graph.nodes.map(n => {
            const p = pos.get(n.id)!;
            const c = colorByLabel.get(n.labels[0] ?? "Unknown")!;
            return (
              <g key={n.id}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={NODE_R}
                  fill={c.fill}
                  stroke={c.stroke}
                  strokeWidth={2}
                />
                <text
                  x={p.x}
                  y={p.y - 2}
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight={600}
                  fill={c.text}
                  fontFamily="ui-sans-serif, system-ui, sans-serif"
                >
                  {truncate(n.caption, 10)}
                </text>
                <text
                  x={p.x}
                  y={p.y + 12}
                  textAnchor="middle"
                  fontSize="9"
                  fill={c.text}
                  opacity={0.75}
                  fontFamily="ui-sans-serif, system-ui, sans-serif"
                >
                  :{n.labels[0] ?? "Node"}
                </text>
              </g>
            );
          })}
        </g>

        {/* Легенда */}
        <g transform={`translate(12, ${VIEW_H - 24})`}>
          {labels.map((lbl, i) => {
            const c = colorByLabel.get(lbl)!;
            const count = groups.get(lbl)!.length;
            return (
              <g key={lbl} transform={`translate(${i * 95}, 0)`}>
                <circle cx={6} cy={6} r={5.5} fill={c.fill} stroke={c.stroke} strokeWidth={1.5} />
                <text
                  x={18}
                  y={10}
                  fontSize={11}
                  fill="#475569"
                  fontFamily="ui-sans-serif, system-ui, sans-serif"
                >
                  :{lbl} ({count})
                </text>
              </g>
            );
          })}
        </g>

        <text
          x={VIEW_W - 12}
          y={VIEW_H - 14}
          textAnchor="end"
          fontSize="10"
          fill="#94a3b8"
          fontFamily="ui-sans-serif, system-ui, sans-serif"
        >
          {graph.nodes.length} узл{nodeSuffix(graph.nodes.length)} ·{" "}
          {graph.edges.length} связ{edgeSuffix(graph.edges.length)}
        </text>
      </svg>
    </div>
  );
}


// ───────── утилиты ─────────

/** Обрезает конец отрезка так, чтобы он касался границы круга цели, а не центра. */
function trimToCircle(s: { x: number; y: number }, t: { x: number; y: number }, r: number) {
  const dx = t.x - s.x;
  const dy = t.y - s.y;
  const len = Math.hypot(dx, dy) || 1;
  const ratio = (len - r - 4) / len;  // -4 чтобы стрелка не утопала в узле
  return {
    x2: s.x + dx * ratio,
    y2: s.y + dy * ratio,
  };
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function nodeSuffix(n: number): string {
  const last = n % 10;
  const teen = n % 100 >= 11 && n % 100 <= 14;
  if (teen) return "ов";
  if (last === 1) return "";
  if (last >= 2 && last <= 4) return "а";
  return "ов";
}

function edgeSuffix(n: number): string {
  const last = n % 10;
  const teen = n % 100 >= 11 && n % 100 <= 14;
  if (teen) return "ей";
  if (last === 1) return "ь";
  if (last >= 2 && last <= 4) return "и";
  return "ей";
}


/** Проверка «есть ли в результате хоть один узел». Используется снаружи, чтобы решить, активна ли вкладка «Граф». */
export function hasGraphData(data: unknown): boolean {
  if (!Array.isArray(data)) return false;
  for (const record of data) {
    if (record === null || typeof record !== "object") continue;
    for (const v of Object.values(record as Record<string, unknown>)) {
      if (isNode(v)) return true;
    }
  }
  return false;
}
