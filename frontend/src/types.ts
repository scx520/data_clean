export type RuleType = 'trim' | 'fill' | 'dedupe' | 'replace' | 'case' | 'convert' | 'validate'
export interface Rule {
  id: string
  type: RuleType
  enabled: boolean
  fields: string[]
  options: Record<string, string>
}
export interface Dataset {
  id: string
  name: string
  row_count: number
  column_count: number
  created_at: string
  source: string
  columns: string[]
}
export interface Quality {
  rows: number
  columns: number
  missing_cells: number
  duplicate_rows: number
  score: number
  field_missing: Record<string, number>
}
export interface Row {
  _row_id: number
  [key: string]: string | number
}
export interface Change {
  row_id: number
  field: string
  before: string
  after: string
  rule: string
  action: string
}
export interface Issue {
  row_id: number
  field: string
  value: string
  rule: string
  reason: string
}
export interface RuleStat {
  index: number
  name: string
  changes: number
  issues: number
  fields?: string[]
  removed_rows?: number
}
export interface Result {
  preview_id: string
  rows: Row[]
  columns: string[]
  changes: Change[]
  issues: Issue[]
  before: Quality
  after: Quality
  rule_stats: RuleStat[]
  total_changes: number
  total_issues: number
}
export interface Task {
  id: string
  name: string
  dataset_id: string
  dataset_name: string
  status: 'pending' | 'running' | 'success' | 'failed'
  created_at: string
  finished_at: string | null
  rules: Rule[]
  error: string | null
  summary: {
    before: Quality
    after: Quality
    changes: number
    issues: number
    rule_stats: RuleStat[]
  } | null
}
export interface Template {
  id: string
  name: string
  description: string
  rules: Rule[]
  created_at: string
}
