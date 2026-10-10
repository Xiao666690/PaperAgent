export interface ComparisonTable { columns: string[]; rows: Array<Record<string, unknown>> }

function validate(value: unknown): ComparisonTable | null {
  if (!value || typeof value !== 'object') return null
  const data = value as Record<string, unknown>
  if (!Array.isArray(data.columns) || !data.columns.length || !Array.isArray(data.rows)) return null
  if (!data.columns.every(col => typeof col === 'string' && col.trim())) return null
  const columns = data.columns as string[]
  if (new Set(columns).size !== columns.length) return null
  const rows: Array<Record<string, unknown>> = []
  for (const row of data.rows) {
    if (Array.isArray(row)) {
      if (row.length !== columns.length) return null
      rows.push(Object.fromEntries(columns.map((col, index) => [col, row[index]])))
    } else if (row && typeof row === 'object') rows.push(row as Record<string, unknown>)
    else return null
  }
  return { columns, rows }
}

export function parseComparisonTable(data: Record<string, unknown>): ComparisonTable | null {
  const direct = validate(data)
  if (direct) return direct
  for (const value of [data.raw, data.comparison, data.markdown]) {
    if (typeof value !== 'string') continue
    const candidates = [value.trim(), ...Array.from(value.matchAll(/```(?:json)?\s*\n?([\s\S]*?)```/gi), match => match[1].trim())]
    for (const candidate of candidates) {
      try {
        let parsed = JSON.parse(candidate)
        if (typeof parsed === 'string') parsed = JSON.parse(parsed)
        const table = validate(parsed)
        if (table) return table
      } catch { /* Preserve the original output if it is malformed; never guess its contents. */ }
    }
  }
  return null
}

export function comparisonColumnLabel(column: string): string {
  const labels: Record<string, string> = { paper: '论文', papers: '论文', title: '论文', method: '方法', methods: '方法', dataset: '数据集', datasets: '数据集', metric: '评估指标', metrics: '评估指标', findings: '主要发现', limitations: '局限性' }
  return Object.prototype.hasOwnProperty.call(labels, column.toLowerCase()) ? labels[column.toLowerCase()] : column
}

export function formatComparisonCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.length ? value.map(formatComparisonCell).join('\n') : '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
