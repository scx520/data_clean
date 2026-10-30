<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock3,
  Database,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Filter,
  FolderOpen,
  History,
  Info,
  Layers3,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  MoreHorizontal,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import { api, download } from './api'
import ClusterReport from './components/ClusterReport.vue'
import type {
  Change,
  Dataset,
  Issue,
  Quality,
  Result,
  Row,
  Rule,
  RuleType,
  Task,
  Template,
} from './types'

type Page = 'workspace' | 'datasets' | 'tasks' | 'templates' | 'reports'
const navigation = [
  { id: 'workspace' as Page, label: '清洗工作台', icon: LayoutDashboard },
  { id: 'datasets' as Page, label: '数据集管理', icon: Database },
  { id: 'tasks' as Page, label: '任务记录', icon: ClipboardList },
  { id: 'templates' as Page, label: '规则模板', icon: Layers3 },
  { id: 'reports' as Page, label: '质量报告', icon: FileCheck2 },
]
const ruleTypes: { type: RuleType; title: string; description: string; category: string }[] = [
  {
    type: 'cluster',
    title: '聚类分析',
    description: '按数值或中文文本相似度分组，新增分组标签',
    category: 'AI 分析',
  },
  {
    type: 'trim',
    title: '去除首尾空格',
    description: '清理字段两端多余的空白字符',
    category: '文本整理',
  },
  { type: 'fill', title: '填充缺失值', description: '使用指定内容补全空值', category: '缺失处理' },
  {
    type: 'dedupe',
    title: '去除重复记录',
    description: '按选定字段去重，保留第一条',
    category: '重复处理',
  },
  {
    type: 'replace',
    title: '文本替换',
    description: '查找并替换字段中的指定文本',
    category: '文本整理',
  },
  {
    type: 'case',
    title: '统一英文大小写',
    description: '将英文文本转换为大写或小写',
    category: '格式规范',
  },
  {
    type: 'convert',
    title: '转换字段格式',
    description: '统一日期格式或数值格式',
    category: '格式规范',
  },
  {
    type: 'validate',
    title: '标记异常数据',
    description: '检查手机号或邮箱格式并记录异常',
    category: '质量校验',
  },
]
const page = ref<Page>('workspace')
const datasets = ref<Dataset[]>([]),
  trashedDatasets = ref<Dataset[]>([]),
  tasks = ref<Task[]>([]),
  templates = ref<Template[]>([])
const selectedId = ref(''),
  rawRows = ref<Row[]>([]),
  columns = ref<string[]>([])
const resultColumns = ref<string[]>([])
const tableColumns = computed(() =>
  tab.value === 'original' ? columns.value : resultColumns.value,
)
const originalQuality = ref<Quality | null>(null),
  rawTotal = ref(0)
const rules = ref<Rule[]>([]),
  expandedRule = ref('')
const preview = ref<Result | null>(null),
  completedTask = ref<Task | null>(null)
const tab = ref<'original' | 'preview' | 'changes' | 'issues'>('original')
const search = ref(''),
  pageNumber = ref(1),
  loading = ref(false),
  busy = ref(''),
  online = ref(false)
const uploadOpen = ref(false),
  rulesOpen = ref(false),
  templateOpen = ref(false),
  helpOpen = ref(false),
  exportOpen = ref(false)
const dragOver = ref(false),
  chosenFile = ref<File | null>(null),
  uploadError = ref('')
const templateName = ref(''),
  templateDescription = ref(''),
  toast = ref<{ text: string; error: boolean } | null>(null)
const activeReport = ref<Task | null>(null),
  resultItems = ref<(Row | Change | Issue)[]>([]),
  resultTotal = ref(0)
const fileInput = ref<HTMLInputElement | null>(null)
const datasetView = ref<'active' | 'trash'>('active')
const datasetToDelete = ref<Dataset | null>(null)
const deletionTaskCount = computed(
  () => tasks.value.filter((task) => task.dataset_id === datasetToDelete.value?.id).length,
)
const displayedDatasets = computed(() =>
  datasetView.value === 'active' ? datasets.value : trashedDatasets.value,
)
let toastTimer: ReturnType<typeof setTimeout>,
  searchTimer: ReturnType<typeof setTimeout>,
  pollTimer: ReturnType<typeof setInterval> | undefined
let dataRevision = 0,
  originalRevision = 0,
  resultRevision = 0
const currentDataset = computed(() =>
  [...datasets.value, ...trashedDatasets.value].find((d) => d.id === selectedId.value),
)
const title = computed(() => navigation.find((n) => n.id === page.value)?.label)
const currentQuality = computed(() =>
  tab.value === 'original'
    ? originalQuality.value
    : completedTask.value?.summary?.after || preview.value?.after || originalQuality.value,
)
const enabledCount = computed(() => rules.value.filter((r) => r.enabled).length)
const successfulTasks = computed(() => tasks.value.filter((t) => t.status === 'success'))
const isRunning = computed(() =>
  ['preview', 'run', 'upload', 'dataset-delete', 'dataset-restore'].includes(busy.value),
)
const hasResult = computed(() => !!preview.value || !!completedTask.value)
const resultIsSaved = computed(() => !!completedTask.value)
const visibleRows = computed(() =>
  tab.value === 'original' ? rawRows.value : (resultItems.value as Row[]),
)
const visibleChanges = computed(() => resultItems.value as Change[])
const visibleIssues = computed(() => resultItems.value as Issue[])
const shownTotal = computed(() => (tab.value === 'original' ? rawTotal.value : resultTotal.value))
const totalPages = computed(() => Math.max(1, Math.ceil(shownTotal.value / 50)))
const changeCount = computed(
  () => completedTask.value?.summary?.changes ?? preview.value?.total_changes ?? 0,
)
const issueCount = computed(
  () => completedTask.value?.summary?.issues ?? preview.value?.total_issues ?? 0,
)
const resultSummary = computed(() => completedTask.value?.summary || preview.value)
const removedRowCount = computed(() =>
  resultSummary.value ? resultSummary.value.before.rows - resultSummary.value.after.rows : 0,
)
const annotatedCellCount = computed(
  () =>
    resultSummary.value?.rule_stats.reduce((sum, stat) => sum + (stat.annotated_cells || 0), 0) ||
    0,
)
const modifiedCellCount = computed(
  () => changeCount.value - removedRowCount.value - annotatedCellCount.value,
)
function notify(text: string, error = false) {
  toast.value = { text, error }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = null), 4500)
}
function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}
function number(value?: number) {
  return (value ?? 0).toLocaleString('zh-CN')
}
function date(value: string) {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
function statusName(status: string) {
  return (
    (
      { pending: '等待执行', running: '执行中', success: '已完成', failed: '执行失败' } as Record<
        string,
        string
      >
    )[status] || status
  )
}
function ruleMeta(type: RuleType) {
  return ruleTypes.find((r) => r.type === type)!
}
function newRule(type: RuleType): Rule {
  const fields = columns.value
  const preferred = (name: string) => (fields.includes(name) ? [name] : fields.slice(0, 1))
  if (type === 'cluster') {
    let output = '聚类分组'
    let suffix = 2
    const used = [
      ...fields,
      ...rules.value.filter((r) => r.type === 'cluster').map((r) => r.options.output),
    ]
    while (used.includes(output)) output = `聚类分组${suffix++}`
    return {
      id: crypto.randomUUID(),
      type,
      enabled: true,
      fields: fields.includes('消费金额') ? ['消费金额'] : fields.slice(0, 1),
      options: { mode: fields.includes('消费金额') ? 'numeric' : 'text', clusters: '3', output },
    }
  }
  return {
    id: crypto.randomUUID(),
    type,
    enabled: true,
    fields:
      type === 'trim' || type === 'dedupe'
        ? []
        : preferred(
            type === 'fill'
              ? '所属城市'
              : type === 'case'
                ? '邮箱'
                : type === 'convert'
                  ? '注册日期'
                  : type === 'validate'
                    ? '手机号'
                    : '客户姓名',
          ),
    options:
      type === 'fill'
        ? { value: '未填写' }
        : type === 'case'
          ? { mode: 'lower' }
          : type === 'convert'
            ? { format: 'date' }
            : type === 'validate'
              ? { format: 'phone' }
              : type === 'replace'
                ? { search: '', replacement: '' }
                : {},
  }
}
function resetRules() {
  rules.value = ['trim', 'fill', 'dedupe'].map((type) => newRule(type as RuleType))
  expandedRule.value = rules.value[0]?.id || ''
}
function addRule(type: RuleType) {
  const rule = newRule(type)
  rules.value.push(rule)
  expandedRule.value = rule.id
  rulesOpen.value = false
}
function moveRule(index: number, direction: number) {
  const other = index + direction
  if (other < 0 || other >= rules.value.length) return
  const item = rules.value.splice(index, 1)[0]!
  rules.value.splice(other, 0, item)
}
function toggleField(rule: Rule, field: string) {
  rule.fields = rule.fields.includes(field)
    ? rule.fields.filter((f) => f !== field)
    : [...rule.fields, field]
}

async function refreshCollections() {
  const [ds, ts, rs, deleted] = await Promise.all([
    api<Dataset[]>('/datasets'),
    api<Task[]>('/tasks'),
    api<Template[]>('/templates'),
    api<Dataset[]>('/datasets?deleted=true'),
  ])
  datasets.value = ds
  tasks.value = ts
  templates.value = rs
  trashedDatasets.value = deleted
}
async function deleteDataset() {
  const dataset = datasetToDelete.value
  if (!dataset || isRunning.value) return
  busy.value = 'dataset-delete'
  try {
    await api(`/datasets/${dataset.id}`, { method: 'DELETE' })
    datasetToDelete.value = null
    await refreshCollections()
    if (selectedId.value === dataset.id) await selectDataset(datasets.value[0]?.id || '')
    notify('数据集已移入回收站，可随时恢复；历史任务与结果已保留')
  } catch (error) {
    notify(errorMessage(error), true)
  } finally {
    busy.value = ''
  }
}
async function restoreDataset(dataset: Dataset) {
  if (isRunning.value) return
  busy.value = 'dataset-restore'
  try {
    await api(`/datasets/${dataset.id}/restore`, { method: 'POST' })
    await refreshCollections()
    if (!selectedId.value) await selectDataset(dataset.id)
    notify(`已恢复「${dataset.name}」`)
  } catch (error) {
    notify(errorMessage(error), true)
  } finally {
    busy.value = ''
  }
}
async function loadOriginal() {
  if (!selectedId.value) return
  const revision = ++originalRevision
  loading.value = true
  try {
    const data = await api<Dataset & { rows: Row[]; quality: Quality; total: number }>(
      `/datasets/${selectedId.value}?page=${pageNumber.value}&search=${encodeURIComponent(search.value)}`,
    )
    if (revision !== originalRevision) return
    rawRows.value = data.rows
    columns.value = data.columns
    originalQuality.value = data.quality
    rawTotal.value = data.total
  } catch (error) {
    if (revision === originalRevision) notify(errorMessage(error), true)
  } finally {
    if (revision === originalRevision) loading.value = false
  }
}
async function loadResult() {
  if (!hasResult.value || tab.value === 'original') return
  const revision = ++resultRevision
  loading.value = true
  try {
    const view = tab.value === 'preview' ? 'rows' : tab.value
    const endpoint = completedTask.value
      ? `/tasks/${completedTask.value.id}/result`
      : `/previews/${preview.value!.preview_id}`
    const data = await api<{ items: (Row | Change | Issue)[]; total: number; columns: string[] }>(
      `${endpoint}?view=${view}&page=${pageNumber.value}&search=${encodeURIComponent(search.value)}`,
    )
    if (revision !== resultRevision) return
    resultItems.value = data.items
    resultColumns.value = data.columns
    resultTotal.value = data.total
  } catch (error) {
    if (revision === resultRevision) notify(errorMessage(error), true)
  } finally {
    if (revision === resultRevision) loading.value = false
  }
}
async function selectDataset(identity: string, retainRules = false) {
  dataRevision++
  originalRevision++
  resultRevision++
  selectedId.value = identity
  preview.value = null
  completedTask.value = null
  resultItems.value = []
  resultColumns.value = []
  resultTotal.value = 0
  rawTotal.value = 0
  originalQuality.value = null
  tab.value = 'original'
  pageNumber.value = 1
  search.value = ''
  columns.value = currentDataset.value?.columns || []
  rawRows.value = []
  if (!retainRules) resetRules()
  await loadOriginal()
}
async function updateTable() {
  if (tab.value === 'original') await loadOriginal()
  else if (hasResult.value) await loadResult()
}
function setTab(value: typeof tab.value) {
  if (value !== 'original' && !hasResult.value) return
  tab.value = value
  pageNumber.value = 1
  search.value = ''
  resultItems.value = []
  resultTotal.value =
    value === 'preview'
      ? resultSummary.value?.after.rows || 0
      : value === 'changes'
        ? changeCount.value
        : value === 'issues'
          ? issueCount.value
          : 0
  void updateTable()
}
function goPage(value: number) {
  pageNumber.value = value
  void updateTable()
}

async function uploadFile() {
  if (!chosenFile.value || isRunning.value) return
  busy.value = 'upload'
  uploadError.value = ''
  try {
    const form = new FormData()
    form.append('file', chosenFile.value)
    const data = await api<{ id: string }>('/datasets', { method: 'POST', body: form })
    await refreshCollections()
    await selectDataset(data.id)
    page.value = 'workspace'
    uploadOpen.value = false
    chosenFile.value = null
    notify('数据导入成功，可以开始配置清洗规则')
  } catch (error) {
    uploadError.value = errorMessage(error)
  } finally {
    busy.value = ''
  }
}
function chooseFile(file?: File) {
  if (!file) return
  if (!/\.(csv|xlsx)$/i.test(file.name)) {
    uploadError.value = '请选择 CSV 或 XLSX 文件'
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    uploadError.value = '文件大小不能超过 20 MB'
    return
  }
  chosenFile.value = file
  uploadError.value = ''
}
function onDrop(event: DragEvent) {
  dragOver.value = false
  chooseFile(event.dataTransfer?.files[0])
}

async function makePreview() {
  if (!selectedId.value || currentDataset.value?.deleted_at || isRunning.value) return
  busy.value = 'preview'
  const revision = dataRevision
  try {
    const result = await api<Result>(`/datasets/${selectedId.value}/preview`, {
      method: 'POST',
      body: JSON.stringify({ rules: rules.value }),
    })
    if (revision !== dataRevision) return
    preview.value = result
    resultColumns.value = result.columns
    completedTask.value = null
    setTab('preview')
    notify(
      `预览完成：${number(result.before.rows)} → ${number(result.after.rows)} 行，移除 ${number(result.before.rows - result.after.rows)} 行，${number(result.total_changes)} 处变更，${number(result.total_issues)} 项异常`,
    )
  } catch (error) {
    notify(errorMessage(error), true)
  } finally {
    busy.value = ''
  }
}
async function runTask() {
  if (!selectedId.value || currentDataset.value?.deleted_at || isRunning.value) return
  busy.value = 'run'
  const revision = dataRevision
  try {
    const response = await api<{ id: string }>(`/datasets/${selectedId.value}/tasks`, {
      method: 'POST',
      body: JSON.stringify({
        rules: rules.value,
        name: `${currentDataset.value?.name.replace(/\.[^.]+$/, '')} · 清洗任务`,
      }),
    })
    notify('清洗任务已提交，正在处理数据')
    startPolling(response.id, revision)
  } catch (error) {
    notify(errorMessage(error), true)
    busy.value = ''
  }
}
function startPolling(identity: string, revision: number) {
  if (pollTimer) clearInterval(pollTimer)
  let polling = false
  pollTimer = setInterval(async () => {
    if (polling) return
    polling = true
    try {
      const task = await api<Task>(`/tasks/${identity}`)
      if (!['success', 'failed'].includes(task.status)) return
      clearInterval(pollTimer)
      pollTimer = undefined
      busy.value = ''
      await refreshCollections()
      if (task.status === 'failed') {
        notify(task.error || '清洗失败', true)
        return
      }
      if (revision === dataRevision) {
        completedTask.value = task
        preview.value = null
        setTab('preview')
      }
      notify('清洗完成，结果和变更记录已保存，可导出下载')
    } catch (error) {
      clearInterval(pollTimer)
      pollTimer = undefined
      busy.value = ''
      notify(errorMessage(error), true)
    } finally {
      polling = false
    }
  }, 700)
}
async function openTask(task: Task) {
  if (task.status !== 'success') {
    notify(task.error || '该任务尚未完成', true)
    return
  }
  await selectDataset(task.dataset_id, true)
  rules.value = JSON.parse(JSON.stringify(task.rules))
  completedTask.value = task
  page.value = 'workspace'
  setTab('preview')
}
function showReport() {
  activeReport.value = completedTask.value
  page.value = 'reports'
}
function openDataset(identity: string) {
  page.value = 'workspace'
  void selectDataset(identity)
}
async function exportFile(kind = 'data', format = 'csv', task = completedTask.value) {
  if (!task) return
  exportOpen.value = false
  try {
    await download(
      `/tasks/${task.id}/export?kind=${kind}&format=${format}`,
      `${task.dataset_name.replace(/\.[^.]+$/, '')}_${{ data: '清洗结果', changes: '变更记录', issues: '异常记录', report: '质量报告' }[kind] || kind}.${kind === 'report' ? 'json' : format}`,
    )
    notify('文件已开始下载')
  } catch (error) {
    notify(errorMessage(error), true)
  }
}
async function saveTemplate() {
  if (!templateName.value.trim()) return
  busy.value = 'template'
  try {
    await api('/templates', {
      method: 'POST',
      body: JSON.stringify({
        name: templateName.value.trim(),
        description: templateDescription.value.trim(),
        rules: rules.value,
      }),
    })
    await refreshCollections()
    templateOpen.value = false
    templateName.value = ''
    templateDescription.value = ''
    notify('规则模板已保存')
  } catch (error) {
    notify(errorMessage(error), true)
  } finally {
    busy.value = ''
  }
}
function applyTemplate(template: Template) {
  if (!selectedId.value) {
    notify('请先导入或选择一个数据集', true)
    return
  }
  const missing = [
    ...new Set(template.rules.flatMap((r) => r.fields).filter((f) => !columns.value.includes(f))),
  ]
  if (missing.length) {
    notify(`当前数据集缺少字段：${missing.join('、')}，请先选择匹配的数据集`, true)
    return
  }
  rules.value = (JSON.parse(JSON.stringify(template.rules)) as Rule[]).map((r) => ({
    ...r,
    id: crypto.randomUUID(),
  }))
  page.value = 'workspace'
  expandedRule.value = rules.value[0]?.id || ''
  notify(`已应用模板「${template.name}」`)
}
async function removeTemplate(template: Template) {
  if (!window.confirm(`删除模板「${template.name}」？`)) return
  try {
    await api(`/templates/${template.id}`, { method: 'DELETE' })
    await refreshCollections()
    notify('模板已删除')
  } catch (error) {
    notify(errorMessage(error), true)
  }
}
function keyboard(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    uploadOpen.value = false
    rulesOpen.value = false
    templateOpen.value = false
    helpOpen.value = false
    exportOpen.value = false
    if (!isRunning.value) datasetToDelete.value = null
  }
}
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pageNumber.value = 1
    void updateTable()
  }, 280)
})
watch(
  rules,
  () => {
    dataRevision++
    if (hasResult.value) {
      preview.value = null
      completedTask.value = null
      tab.value = 'original'
      pageNumber.value = 1
      void loadOriginal()
    }
  },
  { deep: true, flush: 'sync' },
)
watch(page, () => {
  if (page.value === 'tasks' || page.value === 'reports' || page.value === 'datasets')
    void refreshCollections().catch((error) => notify(errorMessage(error), true))
})
onMounted(async () => {
  document.addEventListener('keydown', keyboard)
  try {
    await api('/health')
    online.value = true
    await refreshCollections()
    if (datasets.value[0]) await selectDataset(datasets.value[0].id)
  } catch (error) {
    notify(`连接服务失败：${errorMessage(error)}`, true)
  }
})
onUnmounted(() => {
  clearTimeout(searchTimer)
  clearTimeout(toastTimer)
  clearInterval(pollTimer)
  document.removeEventListener('keydown', keyboard)
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a href="#" class="brand" @click.prevent="page = 'workspace'"
        ><span class="brand-symbol"><Filter :size="23" :stroke-width="2" /></span
        ><span
          >数据清洗<span class="brand-light">平台</span><small>DATA CLEANING PLATFORM</small></span
        ></a
      >
      <div class="workspace-label">
        <span class="workspace-avatar">工</span>
        <div>默认工作空间<small>本地数据 · 安心管理</small></div>
        <ChevronDown :size="14" />
      </div>
      <div class="nav-label">工作空间</div>
      <nav>
        <button
          v-for="item in navigation"
          :key="item.id"
          :aria-label="item.label"
          :class="['nav-item', { active: page === item.id }]"
          @click="page = item.id"
        >
          <component :is="item.icon" :size="19" /><span>{{ item.label }}</span
          ><span v-if="item.id === 'datasets'" class="nav-count">{{ datasets.length }}</span
          ><span v-if="item.id === 'workspace' && page === item.id" class="nav-active-dot"></span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <div class="local-card">
          <ShieldCheck :size="20" /><strong>数据留在本地</strong>
          <p>原始数据独立保留<br />清洗过程完整可追溯</p>
          <span><i class="status-dot"></i>本地工作模式</span>
        </div>
        <button class="help-link" @click="helpOpen = true">
          <CircleHelp :size="17" />使用指南<ArrowUpRight :size="15" />
        </button>
        <div class="version">通用数据清洗平台 <span>V1.0</span></div>
      </div>
    </aside>

    <main class="main-shell">
      <header class="topbar">
        <div class="breadcrumb">
          工作空间<ChevronRight :size="14" /><span>{{ title }}</span>
        </div>
        <div class="topbar-right">
          <span class="connection"
            ><i :class="['status-dot', { offline: !online }]"></i
            >{{ online ? '服务已连接' : '服务未连接' }}</span
          ><span class="topbar-divider"></span><span class="user-avatar">本</span
          ><span>本地工作空间</span>
        </div>
      </header>
      <div class="page-content">
        <div class="page-heading">
          <div>
            <div class="eyebrow">
              {{ page === 'workspace' ? '让每一份数据，都井然有序' : 'YOUR DATA, WELL ORGANIZED' }}
            </div>
            <h1>
              {{ title }}<span v-if="page === 'workspace'" class="version-tag">WORKBENCH</span>
            </h1>
            <p>
              {{
                page === 'workspace'
                  ? '从杂乱到有序，配置规则、预览效果，轻松完成数据清洗。'
                  : page === 'datasets'
                    ? '集中管理导入的数据文件，随时开启新的清洗任务。'
                    : page === 'tasks'
                      ? '每一次执行都有记录，每一处变更都有依据。'
                      : page === 'templates'
                        ? '把有效的清洗经验保存下来，让下次处理更简单。'
                        : '查看清洗成效，定位数据问题，掌握每一次质量变化。'
              }}
            </p>
          </div>
          <button class="button primary" @click="uploadOpen = true">
            <Upload :size="16" />导入数据
          </button>
        </div>

        <template v-if="page === 'workspace'">
          <div class="workflow">
            <span class="step complete"><span>1</span>导入数据<Check :size="13" /></span>
            <div class="step-line"></div>
            <span class="step current"><span>2</span>配置与清洗</span>
            <div class="step-line"></div>
            <span :class="['step', { current: resultIsSaved }]"><span>3</span>检查与导出</span
            ><span class="workflow-note"><Info :size="14" />清洗不会覆盖原始文件</span>
          </div>
          <div class="metrics">
            <div class="metric">
              <span class="metric-label"
                >数据记录<span class="metric-icon blue"><Database :size="17" /></span
              ></span>
              <div class="metric-value">{{ number(currentQuality?.rows) }}<small>行</small></div>
              <span class="metric-foot"
                >{{ currentQuality?.columns || 0 }} 个原始字段<span
                  v-if="tab !== 'original' && resultColumns.length > columns.length"
                >
                  · {{ resultColumns.length - columns.length }} 个分析字段</span
                ></span
              >
            </div>
            <div class="metric">
              <span class="metric-label"
                >缺失单元格<span class="metric-icon amber"><ListFilter :size="17" /></span
              ></span>
              <div class="metric-value">
                {{ number(currentQuality?.missing_cells) }}<small>个</small>
              </div>
              <span class="metric-foot"
                ><i class="mini-dot amber-dot"></i
                >{{
                  currentQuality?.missing_cells ? '建议配置缺失值处理规则' : '字段内容完整'
                }}</span
              >
            </div>
            <div class="metric">
              <span class="metric-label"
                >重复记录<span class="metric-icon violet"><Layers3 :size="17" /></span
              ></span>
              <div class="metric-value">
                {{ number(currentQuality?.duplicate_rows) }}<small>行</small>
              </div>
              <span class="metric-foot">按全部字段比对重复内容</span>
            </div>
            <div class="metric quality-metric">
              <span class="metric-label"
                >数据完整性评分<span class="metric-icon brand-blue"><ShieldCheck :size="18" /></span
              ></span>
              <div class="metric-value brand-color">
                {{ currentQuality?.score ?? '—' }}<small>/ 100</small>
              </div>
              <div class="score-track">
                <span :style="{ width: `${currentQuality?.score || 0}%` }"></span>
              </div>
            </div>
          </div>

          <div class="workbench-grid">
            <section class="panel data-panel">
              <div class="panel-heading">
                <div class="panel-title">
                  <FileSpreadsheet :size="19" />
                  <h2>数据预览</h2>
                  <span class="subtle-tag">{{
                    currentDataset?.source === 'demo' ? '模拟数据' : '原文件保留'
                  }}</span>
                </div>
                <button
                  class="icon-button"
                  title="刷新数据"
                  aria-label="刷新数据"
                  :disabled="loading"
                  @click="updateTable"
                >
                  <RefreshCw :size="16" :class="{ spinning: loading }" />
                </button>
              </div>
              <div class="dataset-select-row">
                <span class="file-icon"><FileSpreadsheet :size="21" /></span>
                <div class="dataset-selector">
                  <label for="dataset">当前数据集</label
                  ><select
                    id="dataset"
                    :value="selectedId"
                    :disabled="isRunning"
                    @change="selectDataset(($event.target as HTMLSelectElement).value)"
                  >
                    <option v-if="currentDataset?.deleted_at" :value="currentDataset.id">
                      已删除 · {{ currentDataset.name }}
                    </option>
                    <option v-if="!datasets.length && !currentDataset" value="">
                      请先导入数据
                    </option>
                    <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
                      {{ dataset.name }}
                    </option>
                  </select>
                </div>
                <span class="file-type">{{
                  currentDataset?.name.split('.').pop()?.toUpperCase() || 'DATA'
                }}</span>
              </div>
              <div v-if="currentDataset?.deleted_at" class="dataset-archived-notice">
                <Info :size="15" /><span
                  >此数据集已移入回收站。历史结果仍可查看和导出，恢复后可继续清洗。</span
                >
                <button
                  class="text-button"
                  :disabled="isRunning"
                  @click="restoreDataset(currentDataset)"
                >
                  恢复数据集
                </button>
              </div>
              <div class="table-toolbar">
                <div class="tabs">
                  <button :class="{ selected: tab === 'original' }" @click="setTab('original')">
                    原始数据</button
                  ><button
                    :class="{ selected: tab === 'preview' }"
                    :disabled="!hasResult"
                    @click="setTab('preview')"
                  >
                    {{ resultIsSaved ? '清洗结果' : '清洗预览'
                    }}<span v-if="hasResult" class="tab-dot"></span></button
                  ><button
                    :class="{ selected: tab === 'changes' }"
                    :disabled="!hasResult"
                    @click="setTab('changes')"
                  >
                    变更记录<span v-if="hasResult" class="tab-number">{{
                      changeCount
                    }}</span></button
                  ><button
                    v-if="hasResult && issueCount"
                    :class="{ selected: tab === 'issues' }"
                    @click="setTab('issues')"
                  >
                    异常<span class="tab-number">{{ issueCount }}</span>
                  </button>
                </div>
              </div>
              <div class="table-options">
                <div class="table-caption">
                  <span
                    :class="['mini-dot', tab === 'original' ? 'primary-dot' : 'blue-dot']"
                  ></span
                  >{{
                    tab === 'original'
                      ? '原始数据视图'
                      : tab === 'preview'
                        ? resultIsSaved
                          ? '已保存的清洗结果'
                          : '预览结果 · 尚未保存'
                        : tab === 'changes'
                          ? '逐条追踪数据变更'
                          : '需人工核查的异常项'
                  }}
                </div>
                <label class="search-input"
                  ><Search :size="15" /><input
                    v-model="search"
                    placeholder="搜索数据…"
                    aria-label="搜索数据" /><button
                    v-if="search"
                    class="icon-button small"
                    aria-label="清除搜索"
                    @click="search = ''"
                  >
                    <X :size="12" /></button
                ></label>
              </div>
              <div v-if="resultSummary && tab !== 'original'" class="result-summary">
                <div class="result-summary-counts">
                  <span
                    >原始 <strong>{{ number(resultSummary.before.rows) }}</strong> 行</span
                  >
                  <ArrowRight :size="14" />
                  <span
                    >{{ resultIsSaved ? '清洗后' : '预览结果' }}
                    <strong>{{ number(resultSummary.after.rows) }}</strong> 行</span
                  >
                  <span class="summary-detail"
                    >移除 {{ number(removedRowCount) }} 行 · 修改
                    {{ number(modifiedCellCount) }} 个单元格<span v-if="annotatedCellCount">
                      · 新增 {{ number(annotatedCellCount) }} 个标签</span
                    ></span
                  >
                </div>
                <p>
                  {{
                    resultIsSaved
                      ? '完整结果支持分页查看和搜索。'
                      : '已对全部原始数据计算，完整预览支持分页查看和搜索；执行清洗后保存结果。'
                  }}
                </p>
                <p v-if="!changeCount" class="zero-change-hint">
                  本次没有产生变更，可展开下方明细核对实际执行的字段。
                </p>
                <details class="execution-details">
                  <summary>
                    本次实际执行 {{ resultSummary.rule_stats.length }} 条规则 · 查看字段与处理明细
                  </summary>
                  <div
                    v-for="stat in resultSummary.rule_stats"
                    :key="stat.index"
                    class="execution-rule"
                  >
                    <strong>{{ stat.index }}. {{ stat.name }}</strong>
                    <span
                      >处理字段：{{
                        stat.fields?.join('、') || '历史任务未记录字段，请查看规则配置'
                      }}</span
                    >
                    <span
                      >{{ stat.changes }} 处变更<span v-if="stat.removed_rows !== undefined">
                        · 移除 {{ stat.removed_rows }} 行</span
                      >
                      · {{ stat.issues }} 项异常</span
                    >
                  </div>
                </details>
              </div>
              <ClusterReport
                v-if="tab !== 'original' && resultSummary?.analyses?.length"
                :analyses="resultSummary.analyses"
              />
              <div class="table-container" :class="{ 'table-loading': loading }">
                <table v-if="tab === 'original' || tab === 'preview'" class="data-table">
                  <thead>
                    <tr>
                      <th class="row-index">#</th>
                      <th v-for="column in tableColumns" :key="column">
                        <span
                          >{{ column
                          }}<span class="column-type">{{
                            column.includes('金额') ? '#' : column.includes('日期') ? '◷' : 'Aa'
                          }}</span></span
                        >
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in visibleRows" :key="row._row_id">
                      <td class="row-index">{{ row._row_id }}</td>
                      <td
                        v-for="column in tableColumns"
                        :key="column"
                        :class="{ 'missing-cell': !String(row[column] ?? '').trim() }"
                      >
                        <span v-if="!String(row[column] ?? '').trim()" class="empty-value"
                          >空值</span
                        ><span
                          v-else
                          :class="{
                            'level-badge': column === '客户等级',
                            'level-gold': column === '客户等级' && row[column] === '金卡',
                          }"
                          >{{ row[column] }}</span
                        >
                      </td>
                    </tr>
                  </tbody>
                </table>
                <table v-else-if="tab === 'changes'" class="data-table">
                  <thead>
                    <tr>
                      <th>原始行号</th>
                      <th>字段</th>
                      <th>原值</th>
                      <th></th>
                      <th>处理后</th>
                      <th>清洗规则</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(change, i) in visibleChanges" :key="i">
                      <td class="mono"># {{ change.row_id }}</td>
                      <td>{{ change.field }}</td>
                      <td class="before-value">{{ change.before || '（空值）' }}</td>
                      <td><ArrowRight :size="13" class="muted" /></td>
                      <td class="after-value">{{ change.after || '（空值）' }}</td>
                      <td>{{ change.rule }}</td>
                    </tr>
                  </tbody>
                </table>
                <table v-else class="data-table">
                  <thead>
                    <tr>
                      <th>原始行号</th>
                      <th>字段</th>
                      <th>异常值</th>
                      <th>校验规则</th>
                      <th>问题说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(issue, i) in visibleIssues" :key="i">
                      <td class="mono"># {{ issue.row_id }}</td>
                      <td>{{ issue.field }}</td>
                      <td class="before-value">{{ issue.value }}</td>
                      <td>{{ issue.rule }}</td>
                      <td>{{ issue.reason }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="!shownTotal && !loading" class="empty-state table-empty">
                  <Search :size="30" /><strong>{{
                    selectedId
                      ? search
                        ? '没有找到匹配的数据'
                        : '暂无记录'
                      : '从导入第一份数据开始'
                  }}</strong>
                  <p>
                    {{
                      selectedId
                        ? '可以调整搜索条件，或切换其他数据视图。'
                        : '支持 CSV、Excel 文件，也支持拖拽上传。'
                    }}
                  </p>
                  <button v-if="!selectedId" class="button primary" @click="uploadOpen = true">
                    导入数据
                  </button>
                </div>
              </div>
              <div class="table-footer">
                <span
                  >{{ search ? '匹配' : '共' }} <strong>{{ number(shownTotal) }}</strong> 条{{
                    tab === 'original' || tab === 'preview' ? '数据' : '记录'
                  }}<span v-if="shownTotal" class="footer-range"
                    >展示 {{ (pageNumber - 1) * 50 + 1 }}–{{
                      Math.min(pageNumber * 50, shownTotal)
                    }}</span
                  ></span
                >
                <div class="pagination">
                  <span>每页 50 条</span
                  ><button
                    class="icon-button"
                    aria-label="上一页"
                    :disabled="pageNumber <= 1"
                    @click="goPage(pageNumber - 1)"
                  >
                    <ChevronLeft :size="16" /></button
                  ><span class="page-number">{{ pageNumber }}</span
                  ><span class="page-total">/ {{ totalPages }}</span
                  ><button
                    class="icon-button"
                    aria-label="下一页"
                    :disabled="pageNumber >= totalPages"
                    @click="goPage(pageNumber + 1)"
                  >
                    <ChevronRight :size="16" />
                  </button>
                </div>
              </div>
              <div class="data-panel-footnote">
                <ShieldCheck :size="14" /><span>原始行号贯穿整个清洗过程，随时追溯数据来源。</span>
              </div>
            </section>

            <aside class="panel rules-panel">
              <div class="panel-heading">
                <div class="panel-title">
                  <Settings2 :size="18" />
                  <h2>清洗规则</h2>
                  <span class="count-badge">{{ rules.length }}</span>
                </div>
                <button
                  class="text-button"
                  :disabled="!rules.length || isRunning"
                  @click="templateOpen = true"
                >
                  <Save :size="14" />存为模板
                </button>
              </div>
              <div class="rules-description">规则按顺序执行，点击卡片配置处理方式。</div>
              <div class="rules-list">
                <article
                  v-for="(rule, index) in rules"
                  :key="rule.id"
                  :class="[
                    'rule-card',
                    { expanded: expandedRule === rule.id, disabled: !rule.enabled },
                  ]"
                >
                  <div class="rule-card-header">
                    <button
                      class="rule-expand"
                      :disabled="isRunning"
                      @click="expandedRule = expandedRule === rule.id ? '' : rule.id"
                    >
                      <span class="rule-order">{{ String(index + 1).padStart(2, '0') }}</span
                      ><span class="rule-name"
                        >{{ ruleMeta(rule.type).title
                        }}<small
                          >{{ rule.enabled ? '已启用' : '已停用' }} ·
                          {{ rule.fields.length ? rule.fields.join('、') : '全部字段' }}</small
                        ></span
                      ><ChevronDown
                        :size="14"
                        :class="{ rotated: expandedRule === rule.id }"
                      /></button
                    ><button
                      :class="['toggle', { on: rule.enabled }]"
                      :disabled="isRunning"
                      :aria-label="`${rule.enabled ? '停用' : '启用'}${ruleMeta(rule.type).title}`"
                      role="switch"
                      :aria-checked="rule.enabled"
                      @click="rule.enabled = !rule.enabled"
                    >
                      <span></span>
                    </button>
                  </div>
                  <div v-if="expandedRule === rule.id" class="rule-config">
                    <label class="field-label"
                      >{{ rule.type === 'dedupe' ? '判重字段' : '处理字段'
                      }}<span v-if="rule.type === 'trim' || rule.type === 'dedupe'"
                        >不选则使用全部字段</span
                      ></label
                    >
                    <div class="field-chips">
                      <button
                        v-for="field in columns"
                        :key="field"
                        :disabled="isRunning"
                        :class="['field-chip', { chosen: rule.fields.includes(field) }]"
                        :aria-pressed="rule.fields.includes(field)"
                        @click="toggleField(rule, field)"
                      >
                        <Check v-if="rule.fields.includes(field)" :size="11" />{{ field }}</button
                      ><span v-if="!columns.length" class="muted">导入数据后选择字段</span>
                    </div>
                    <template v-if="rule.type === 'cluster'">
                      <label class="field-label" :for="`cluster-mode-${rule.id}`">聚类方式</label>
                      <select
                        :id="`cluster-mode-${rule.id}`"
                        v-model="rule.options.mode"
                        class="form-input"
                        :disabled="isRunning"
                      >
                        <option value="numeric">数值聚类 · 金额、次数等</option>
                        <option value="text">中文文本聚类 · 名称、备注等</option>
                      </select>
                      <label class="field-label" :for="`cluster-count-${rule.id}`">分组数量</label>
                      <select
                        :id="`cluster-count-${rule.id}`"
                        v-model="rule.options.clusters"
                        class="form-input"
                        :disabled="isRunning"
                      >
                        <option v-for="k in 11" :key="k + 1" :value="String(k + 1)">
                          {{ k + 1 }} 组
                        </option>
                      </select>
                      <label class="field-label" :for="`cluster-output-${rule.id}`"
                        >新增分组字段名</label
                      >
                      <input
                        :id="`cluster-output-${rule.id}`"
                        v-model="rule.options.output"
                        class="form-input"
                        maxlength="40"
                        :disabled="isRunning"
                        placeholder="聚类分组"
                      />
                      <p class="config-hint">
                        最多选择 20 个字段。{{
                          rule.options.mode === 'numeric'
                            ? '自动平衡不同数值字段的量纲，空值和非数值记录不参与。'
                            : '按文字片段相似度分组，每字段取前 512 字；适合名称和短文本，不代表语义理解。'
                        }}保留全部记录，新增标签并记录分组概况。
                      </p>
                    </template>
                    <template v-if="rule.type === 'fill'"
                      ><label class="field-label" :for="`fill-${rule.id}`">填充内容</label
                      ><input
                        :id="`fill-${rule.id}`"
                        v-model="rule.options.value"
                        class="form-input"
                        :disabled="isRunning"
                        placeholder="如：未填写" /></template
                    ><template v-if="rule.type === 'replace'"
                      ><label class="field-label" :for="`search-${rule.id}`">查找内容</label
                      ><input
                        :id="`search-${rule.id}`"
                        v-model="rule.options.search"
                        class="form-input"
                        :disabled="isRunning"
                        placeholder="输入待替换的文本" /><label
                        class="field-label"
                        :for="`replace-${rule.id}`"
                        >替换为</label
                      ><input
                        :id="`replace-${rule.id}`"
                        v-model="rule.options.replacement"
                        class="form-input"
                        :disabled="isRunning"
                        placeholder="留空表示删除匹配内容" /></template
                    ><template v-if="rule.type === 'case'"
                      ><label class="field-label" :for="`case-${rule.id}`">转换方式</label
                      ><select
                        :id="`case-${rule.id}`"
                        v-model="rule.options.mode"
                        class="form-input"
                        :disabled="isRunning"
                      >
                        <option value="lower">全部转为小写</option>
                        <option value="upper">全部转为大写</option>
                      </select></template
                    ><template v-if="rule.type === 'convert'"
                      ><label class="field-label" :for="`convert-${rule.id}`">目标格式</label
                      ><select
                        :id="`convert-${rule.id}`"
                        v-model="rule.options.format"
                        class="form-input"
                        :disabled="isRunning"
                      >
                        <option value="date">日期：YYYY-MM-DD</option>
                        <option value="number">标准数值：去除千分位</option>
                      </select>
                      <p class="config-hint">无法转换的值会保留原值并列入异常记录。</p></template
                    ><template v-if="rule.type === 'validate'"
                      ><label class="field-label" :for="`validate-${rule.id}`">校验格式</label
                      ><select
                        :id="`validate-${rule.id}`"
                        v-model="rule.options.format"
                        class="form-input"
                        :disabled="isRunning"
                      >
                        <option value="phone">中国大陆手机号</option>
                        <option value="email">电子邮箱</option>
                      </select>
                      <p class="config-hint">仅标记异常，不修改或删除数据。</p></template
                    >
                    <p v-if="rule.type === 'dedupe'" class="config-hint">
                      {{
                        rule.fields.length
                          ? `仅按「${rule.fields.join('、')}」判重，其他字段即使不同，也只保留第一条。`
                          : `按全部 ${columns.length} 个字段联合判重，所有字段都一致才会移除重复行。`
                      }}
                    </p>
                    <p v-if="rule.type === 'trim'" class="config-hint">
                      清理文本两端的空格、换行和制表符。
                    </p>
                    <div class="rule-actions">
                      <span>{{ ruleMeta(rule.type).category }}</span
                      ><button
                        class="icon-button small"
                        :disabled="index === 0 || isRunning"
                        aria-label="上移规则"
                        @click="moveRule(index, -1)"
                      >
                        <ArrowUp :size="13" /></button
                      ><button
                        class="icon-button small"
                        :disabled="index === rules.length - 1 || isRunning"
                        aria-label="下移规则"
                        @click="moveRule(index, 1)"
                      >
                        <ArrowDown :size="13" /></button
                      ><button
                        class="icon-button small danger"
                        :disabled="isRunning"
                        aria-label="删除规则"
                        @click="rules.splice(index, 1)"
                      >
                        <Trash2 :size="13" />
                      </button>
                    </div>
                  </div>
                </article>
                <button
                  class="add-rule-button"
                  :disabled="rules.length >= 30 || isRunning"
                  @click="rulesOpen = true"
                >
                  <Plus :size="16" />添加清洗规则
                </button>
              </div>
              <div class="rule-tip">
                <Sparkles :size="16" />
                <p>
                  <strong>先预览，再执行</strong>预览会应用全部启用规则，确认效果后再保存清洗结果。
                </p>
              </div>
              <div class="rules-panel-footer">
                <span class="enabled-caption"
                  ><span class="mini-dot primary-dot"></span>已启用 {{ enabledCount }} 条规则</span
                >
                <div class="rule-main-actions">
                  <button
                    class="button"
                    :disabled="
                      !selectedId || !!currentDataset?.deleted_at || !enabledCount || isRunning
                    "
                    @click="makePreview"
                  >
                    <LoaderCircle v-if="busy === 'preview'" :size="15" class="spinning" /><Search
                      v-else
                      :size="15"
                    />预览效果</button
                  ><button
                    class="button primary"
                    :disabled="
                      !selectedId || !!currentDataset?.deleted_at || !enabledCount || isRunning
                    "
                    @click="runTask"
                  >
                    <LoaderCircle v-if="busy === 'run'" :size="15" class="spinning" /><Play
                      v-else
                      :size="15"
                    />{{ busy === 'run' ? '清洗中' : '执行清洗' }}
                  </button>
                </div>
              </div>
            </aside>
          </div>
          <div class="bottom-strip">
            <span
              ><CheckCheck :size="16" />{{
                resultIsSaved
                  ? `清洗完成 · ${number(changeCount)} 处变更 · ${number(issueCount)} 项异常`
                  : '准备就绪，选择规则后即可开始清洗'
              }}</span
            >
            <div v-if="resultIsSaved" class="export-wrap">
              <button class="button" @click="showReport">
                <FileCheck2 :size="15" />查看质量报告</button
              ><button class="button primary" @click="exportOpen = !exportOpen">
                <Download :size="15" />导出结果<ChevronDown :size="13" />
              </button>
              <div v-if="exportOpen" class="dropdown-menu">
                <button @click="exportFile('data', 'xlsx')">清洗结果 · Excel</button
                ><button @click="exportFile('data', 'csv')">清洗结果 · CSV</button
                ><button @click="exportFile('changes')">变更记录 · CSV</button
                ><button @click="exportFile('issues')">异常记录 · CSV</button>
              </div>
            </div>
            <span v-else class="muted">CSV / XLSX · 最多 100,000 行</span>
          </div>
        </template>

        <template v-else-if="page === 'datasets'"
          ><div class="section-toolbar">
            <div class="dataset-view-tabs" role="tablist" aria-label="数据集列表">
              <button
                role="tab"
                :aria-selected="datasetView === 'active'"
                :class="{ selected: datasetView === 'active' }"
                @click="datasetView = 'active'"
              >
                全部数据集 <span class="subtle-tag">{{ datasets.length }}</span>
              </button>
              <button
                role="tab"
                :aria-selected="datasetView === 'trash'"
                :class="{ selected: datasetView === 'trash' }"
                @click="datasetView = 'trash'"
              >
                <Trash2 :size="14" />回收站
                <span class="subtle-tag">{{ trashedDatasets.length }}</span>
              </button>
            </div>
            <span class="muted">删除后可从回收站恢复，关联历史任务与结果保留</span>
          </div>
          <div class="dataset-grid">
            <article
              v-for="dataset in displayedDatasets"
              :key="dataset.id"
              class="panel dataset-card"
            >
              <div class="dataset-card-top">
                <span class="large-file-icon"><FileSpreadsheet :size="28" /></span
                ><span class="subtle-tag">{{
                  dataset.deleted_at
                    ? '已删除'
                    : dataset.source === 'demo'
                      ? '模拟数据'
                      : dataset.name.split('.').pop()?.toUpperCase()
                }}</span>
              </div>
              <h3>{{ dataset.name }}</h3>
              <p>
                {{ number(dataset.row_count) }} 行数据<span>·</span
                >{{ dataset.column_count }} 个字段
              </p>
              <div class="dataset-fields">
                <span v-for="field in dataset.columns.slice(0, 4)" :key="field">{{ field }}</span
                ><span v-if="dataset.columns.length > 4">+{{ dataset.columns.length - 4 }}</span>
              </div>
              <div class="dataset-card-bottom">
                <span
                  >{{ date(dataset.deleted_at || dataset.created_at) }}
                  {{ dataset.deleted_at ? '删除' : '导入' }}</span
                >
                <div class="dataset-card-actions">
                  <button
                    v-if="dataset.deleted_at"
                    class="text-button"
                    :disabled="isRunning"
                    @click="restoreDataset(dataset)"
                  >
                    <RefreshCw :size="14" />恢复
                  </button>
                  <template v-else>
                    <button
                      class="text-button"
                      :disabled="isRunning"
                      @click="openDataset(dataset.id)"
                    >
                      开始清洗<ArrowRight :size="14" />
                    </button>
                    <button
                      class="text-button danger-text"
                      :disabled="isRunning"
                      :aria-label="`删除数据集 ${dataset.name}`"
                      @click="datasetToDelete = dataset"
                    >
                      <Trash2 :size="14" />删除
                    </button>
                  </template>
                </div>
              </div>
            </article>
            <button
              v-if="datasetView === 'active'"
              class="dataset-add-card"
              @click="uploadOpen = true"
            >
              <span><Plus :size="24" /></span><strong>导入新的数据集</strong
              ><small>CSV 或 Excel，最大 20 MB</small>
            </button>
          </div>
          <div v-if="datasetView === 'trash' && !trashedDatasets.length" class="panel empty-state">
            <Trash2 :size="36" /><strong>回收站是空的</strong>
            <p>删除的数据集会出现在这里，可以随时恢复。</p>
          </div>
        </template>

        <template v-else-if="page === 'tasks'"
          ><section class="panel">
            <div class="panel-heading">
              <div class="panel-title">
                <History :size="18" />
                <h2>清洗任务记录</h2>
                <span class="count-badge">{{ tasks.length }}</span>
              </div>
              <button
                class="button small"
                @click="refreshCollections().catch((error) => notify(errorMessage(error), true))"
              >
                <RefreshCw :size="14" />刷新
              </button>
            </div>
            <div class="record-table-scroll">
              <table class="data-table record-table">
                <thead>
                  <tr>
                    <th>任务名称 / 数据集</th>
                    <th>执行状态</th>
                    <th>清洗规则</th>
                    <th>处理结果</th>
                    <th>创建时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="task in tasks" :key="task.id">
                    <td>
                      <strong>{{ task.name }}</strong
                      ><small class="cell-secondary">{{ task.dataset_name }}</small
                      ><small v-if="task.error" class="error-text">{{ task.error }}</small>
                    </td>
                    <td>
                      <span :class="['status-badge', task.status]"
                        ><i class="mini-dot"></i>{{ statusName(task.status) }}</span
                      >
                    </td>
                    <td>{{ task.rules.filter((r) => r.enabled).length }} 条规则</td>
                    <td>
                      {{
                        task.summary
                          ? `${number(task.summary.after.rows)} 行 / ${number(task.summary.changes)} 处变更`
                          : '—'
                      }}
                    </td>
                    <td class="muted">{{ date(task.created_at) }}</td>
                    <td>
                      <button
                        class="text-button"
                        :disabled="task.status !== 'success'"
                        @click="openTask(task)"
                      >
                        查看结果<ArrowUpRight :size="13" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="!tasks.length" class="empty-state">
              <ClipboardList :size="38" /><strong>还没有清洗任务</strong>
              <p>在工作台执行一次清洗，任务记录就会出现在这里。</p>
              <button class="button primary" @click="page = 'workspace'">
                前往工作台<ArrowRight :size="14" />
              </button>
            </div></section
        ></template>

        <template v-else-if="page === 'templates'"
          ><div class="template-banner">
            <span class="banner-icon"><Layers3 :size="25" /></span>
            <div>
              <h2>一次配置，多次复用</h2>
              <p>在工作台中配置好规则，点击「存为模板」，下次直接应用到字段相同的数据集。</p>
            </div>
            <button class="button" @click="page = 'workspace'">
              配置规则<ArrowRight :size="15" />
            </button>
          </div>
          <div class="dataset-grid">
            <article v-for="template in templates" :key="template.id" class="panel template-card">
              <div class="dataset-card-top">
                <span class="template-icon"><Layers3 :size="23" /></span
                ><button
                  class="icon-button danger"
                  aria-label="删除模板"
                  @click="removeTemplate(template)"
                >
                  <Trash2 :size="16" />
                </button>
              </div>
              <h3>{{ template.name }}</h3>
              <p>{{ template.description || '自定义清洗规则组合' }}</p>
              <div class="template-rule-list">
                <span v-for="(rule, index) in template.rules" :key="rule.id"
                  ><i>{{ index + 1 }}</i
                  >{{ ruleMeta(rule.type).title }}<small v-if="!rule.enabled">已停用</small></span
                >
              </div>
              <div class="dataset-card-bottom">
                <span>{{ template.rules.length }} 条规则</span
                ><button class="text-button" @click="applyTemplate(template)">
                  应用到工作台<ArrowRight :size="14" />
                </button>
              </div>
            </article>
          </div>
          <div v-if="!templates.length" class="panel empty-state">
            <Layers3 :size="38" /><strong>把常用的清洗步骤存为模板</strong>
            <p>模板会保存规则、字段、执行顺序和配置参数。</p>
            <button class="button primary" @click="page = 'workspace'">
              前往配置<ArrowRight :size="14" />
            </button></div
        ></template>

        <template v-else-if="page === 'reports'"
          ><template v-if="successfulTasks.length"
            ><div class="report-selector">
              <label for="report-select">选择任务</label
              ><select
                id="report-select"
                class="form-input"
                :value="activeReport?.id || successfulTasks[0]?.id"
                @change="
                  activeReport =
                    tasks.find((t) => t.id === ($event.target as HTMLSelectElement).value) || null
                "
              >
                <option v-for="task in successfulTasks" :key="task.id" :value="task.id">
                  {{ task.name }} · {{ date(task.created_at) }}
                </option></select
              ><button
                class="button"
                @click="exportFile('report', 'csv', activeReport || successfulTasks[0])"
              >
                <Download :size="15" />下载报告
              </button>
            </div>
            <template
              v-for="report in [activeReport?.summary ? activeReport : successfulTasks[0]!]"
              :key="report.id"
              ><div class="report-hero">
                <div>
                  <span class="eyebrow">DATA QUALITY REPORT</span>
                  <h2>清洗成效，一目了然</h2>
                  <p>
                    {{ report.dataset_name }}<span>·</span
                    >{{ date(report.finished_at || report.created_at) }}
                  </p>
                  <div class="report-facts">
                    <span
                      ><CheckCircle2 :size="16" />{{
                        report.rules.filter((r) => r.enabled).length
                      }}
                      条规则已执行</span
                    ><span
                      ><History :size="16" />{{
                        number(report.summary!.changes)
                      }}
                      处变更可追溯</span
                    >
                  </div>
                </div>
                <div class="report-score">
                  <span>完整性评分</span>
                  <div>
                    <s>{{ report.summary!.before.score }}</s
                    ><ArrowRight :size="24" /><strong>{{ report.summary!.after.score }}</strong>
                  </div>
                  <small>满分 100 · 格式异常另行列示</small>
                </div>
              </div>
              <ClusterReport
                v-if="report.summary?.analyses?.length"
                :analyses="report.summary.analyses"
              />
              <div class="report-metrics">
                <div class="panel report-stat">
                  <span>数据记录</span
                  ><strong>{{ number(report.summary!.after.rows) }}<small>行</small></strong>
                  <p>
                    移除
                    {{ number(report.summary!.before.rows - report.summary!.after.rows) }}
                    条重复记录
                  </p>
                </div>
                <div class="panel report-stat">
                  <span>缺失单元格</span
                  ><strong
                    >{{ number(report.summary!.after.missing_cells) }}<small>个</small></strong
                  >
                  <p>清洗前 {{ number(report.summary!.before.missing_cells) }} 个</p>
                </div>
                <div class="panel report-stat">
                  <span>整行重复记录</span
                  ><strong
                    >{{ number(report.summary!.after.duplicate_rows) }}<small>行</small></strong
                  >
                  <p>清洗前 {{ number(report.summary!.before.duplicate_rows) }} 行</p>
                </div>
                <div class="panel report-stat">
                  <span>规则识别异常</span
                  ><strong :class="{ 'amber-text': report.summary!.issues }"
                    >{{ number(report.summary!.issues) }}<small>项</small></strong
                  >
                  <p>
                    {{ report.summary!.issues ? '保留原始值，建议人工核查' : '本次规则未报告异常' }}
                  </p>
                </div>
              </div>
              <div class="report-detail-grid">
                <section class="panel">
                  <div class="panel-heading">
                    <h2>字段完整率</h2>
                    <span class="subtle-tag">清洗后</span>
                  </div>
                  <div class="field-quality-list">
                    <div
                      v-for="(missingCount, field) in report.summary!.after.field_missing"
                      :key="field"
                      class="field-quality"
                    >
                      <span>{{ field }}</span>
                      <div class="field-track">
                        <i
                          :style="{
                            width: `${report.summary!.after.rows ? (1 - missingCount / report.summary!.after.rows) * 100 : 100}%`,
                          }"
                        ></i>
                      </div>
                      <strong
                        >{{
                          report.summary!.after.rows
                            ? ((1 - missingCount / report.summary!.after.rows) * 100).toFixed(1)
                            : '100.0'
                        }}%</strong
                      >
                    </div>
                  </div>
                </section>
                <section class="panel">
                  <div class="panel-heading">
                    <h2>规则执行明细</h2>
                    <button class="text-button" @click="openTask(report)">
                      查看变更<ArrowUpRight :size="14" />
                    </button>
                  </div>
                  <div class="rule-stats">
                    <div v-for="stat in report.summary!.rule_stats" :key="stat.index">
                      <span class="rule-order">{{ stat.index }}</span
                      ><strong>{{ stat.name }}</strong
                      ><span
                        >{{ number(stat.changes) }} 处变更<small v-if="stat.issues"
                          >{{ stat.issues }} 项异常</small
                        ></span
                      >
                    </div>
                  </div>
                </section>
              </div>
              <div class="report-note">
                <Info :size="16" />
                <p>
                  完整性评分 = 100 × [1 −（缺失单元格数 + 整行重复数 × 字段数）÷ 总单元格数]，最低为
                  0。评分仅衡量缺失和整行重复情况；格式异常由已启用的校验规则单独统计，不代表数据语义准确性。
                </p>
              </div></template
            ></template
          >
          <div v-else class="panel empty-state">
            <FileCheck2 :size="40" /><strong>清洗之后，质量变化看得见</strong>
            <p>执行清洗任务后，将自动生成质量对比和规则执行报告。</p>
            <button class="button primary" @click="page = 'workspace'">
              开始清洗<ArrowRight :size="14" />
            </button></div
        ></template>

        <footer class="page-footer">
          <span>通用数据清洗平台 V1.0</span><span>让数据更干净，让工作更简单。</span>
        </footer>
      </div>
    </main>

    <Transition name="toast"
      ><div v-if="toast" :class="['toast-message', { error: toast.error }]" role="status">
        <Info v-if="toast.error" :size="18" /><CheckCircle2 v-else :size="18" /><span>{{
          toast.text
        }}</span
        ><button class="icon-button small" aria-label="关闭提示" @click="toast = null">
          <X :size="14" />
        </button></div
    ></Transition>

    <div
      v-if="datasetToDelete"
      class="modal-overlay"
      @click.self="!isRunning && (datasetToDelete = null)"
    >
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="delete-dataset-title">
        <header>
          <span class="modal-icon"><Trash2 :size="22" /></span
          ><button
            class="icon-button"
            :disabled="isRunning"
            aria-label="关闭删除窗口"
            @click="datasetToDelete = null"
          >
            <X :size="20" />
          </button>
        </header>
        <h2 id="delete-dataset-title">删除数据集？</h2>
        <p>「{{ datasetToDelete.name }}」将移入回收站，可随时恢复。</p>
        <div class="delete-dataset-facts">
          <FileSpreadsheet :size="20" />
          <div>
            <strong
              >{{ number(datasetToDelete.row_count) }} 行 ·
              {{ datasetToDelete.column_count }} 个字段</strong
            ><span>关联 {{ deletionTaskCount }} 条任务，历史记录与清洗结果继续保留。</span>
          </div>
        </div>
        <footer>
          <button class="button" :disabled="isRunning" @click="datasetToDelete = null">取消</button
          ><button class="button danger-button" :disabled="isRunning" @click="deleteDataset">
            <LoaderCircle v-if="busy === 'dataset-delete'" :size="15" class="spinning" /><Trash2
              v-else
              :size="15"
            />确认删除
          </button>
        </footer>
      </section>
    </div>
    <div v-if="uploadOpen" class="modal-overlay" @click.self="!isRunning && (uploadOpen = false)">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="upload-title">
        <header>
          <span class="modal-icon"><Upload :size="22" /></span
          ><button
            class="icon-button"
            :disabled="isRunning"
            aria-label="关闭导入窗口"
            @click="uploadOpen = false"
          >
            <X :size="20" />
          </button>
        </header>
        <h2 id="upload-title">导入数据</h2>
        <p>上传一份数据文件，开始你的清洗工作。</p>
        <div
          :class="['dropzone', { dragging: dragOver, 'file-chosen': chosenFile }]"
          role="button"
          tabindex="0"
          @click="fileInput?.click()"
          @keydown.enter="fileInput?.click()"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <FileSpreadsheet v-if="chosenFile" :size="36" /><FolderOpen v-else :size="36" /><strong>{{
            chosenFile?.name || '点击选择文件，或拖拽到这里'
          }}</strong
          ><span>{{
            chosenFile
              ? `${(chosenFile.size / 1024).toFixed(1)} KB · 点击重新选择`
              : '支持 .csv、.xlsx，单个文件不超过 20 MB'
          }}</span>
        </div>
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept=".csv,.xlsx"
          :disabled="isRunning"
          @change="chooseFile(($event.target as HTMLInputElement).files?.[0])"
        />
        <div class="upload-tips">
          <Info :size="15" />
          <p>
            首行为字段名称，Excel 默认读取第一个工作表。<br />最多 100,000 行、200 列；CSV 支持
            UTF-8 和 GB18030。
          </p>
        </div>
        <p v-if="uploadError" class="error-banner" role="alert">{{ uploadError }}</p>
        <footer>
          <button class="button" :disabled="isRunning" @click="uploadOpen = false">取消</button
          ><button class="button primary" :disabled="!chosenFile || isRunning" @click="uploadFile">
            <LoaderCircle v-if="busy === 'upload'" :size="16" class="spinning" /><Upload
              v-else
              :size="16"
            />{{ busy === 'upload' ? '正在导入…' : '导入并预览' }}
          </button>
        </footer>
      </section>
    </div>
    <div v-if="rulesOpen" class="modal-overlay" @click.self="rulesOpen = false">
      <section
        class="modal rule-picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rule-title"
      >
        <header>
          <span class="modal-icon"><Settings2 :size="22" /></span
          ><button class="icon-button" aria-label="关闭规则选择" @click="rulesOpen = false">
            <X :size="20" />
          </button>
        </header>
        <h2 id="rule-title">添加清洗规则</h2>
        <p>选择一种处理方式，添加后可配置字段和参数。</p>
        <div class="rule-picker-list">
          <button v-for="item in ruleTypes" :key="item.type" @click="addRule(item.type)">
            <span class="picker-rule-icon"
              ><component
                :is="
                  item.type === 'dedupe'
                    ? Layers3
                    : item.type === 'validate'
                      ? ShieldCheck
                      : item.type === 'fill'
                        ? Plus
                        : Settings2
                "
                :size="19" /></span
            ><span
              ><strong>{{ item.title }}</strong
              ><small>{{ item.description }}</small></span
            ><Plus :size="17" />
          </button>
        </div>
      </section>
    </div>
    <div v-if="templateOpen" class="modal-overlay" @click.self="templateOpen = false">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="template-title">
        <header>
          <span class="modal-icon"><Layers3 :size="22" /></span
          ><button class="icon-button" aria-label="关闭模板窗口" @click="templateOpen = false">
            <X :size="20" />
          </button>
        </header>
        <h2 id="template-title">保存规则模板</h2>
        <p>将当前 {{ rules.length }} 条规则及其配置保存，方便重复使用。</p>
        <label for="template-name" class="field-label">模板名称</label
        ><input
          id="template-name"
          v-model="templateName"
          class="form-input"
          maxlength="100"
          placeholder="如：客户信息标准化清洗"
        /><label for="template-description" class="field-label">用途说明 <span>选填</span></label
        ><textarea
          id="template-description"
          v-model="templateDescription"
          class="form-input"
          maxlength="500"
          rows="3"
          placeholder="描述这个模板适合处理的数据"
        />
        <footer>
          <button class="button" @click="templateOpen = false">取消</button
          ><button
            class="button primary"
            :disabled="!templateName.trim() || busy === 'template'"
            @click="saveTemplate"
          >
            <Save :size="15" />保存模板
          </button>
        </footer>
      </section>
    </div>
    <div v-if="helpOpen" class="modal-overlay" @click.self="helpOpen = false">
      <section
        class="modal help-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
      >
        <header>
          <span class="modal-icon"><BookOpen :size="22" /></span
          ><button class="icon-button" aria-label="关闭使用指南" @click="helpOpen = false">
            <X :size="20" />
          </button>
        </header>
        <h2 id="help-title">几步，让数据井然有序</h2>
        <ol>
          <li>
            <strong>导入数据</strong>
            <p>上传 CSV 或 Excel，或使用内置的模拟客户表体验。</p>
          </li>
          <li>
            <strong>配置规则</strong>
            <p>选择处理字段，设置规则参数，调整执行顺序。可将规则组合存为模板。</p>
          </li>
          <li>
            <strong>预览效果</strong>
            <p>对比原始数据、清洗预览和变更记录。修改规则后需重新预览。</p>
          </li>
          <li>
            <strong>执行与导出</strong>
            <p>执行后保存完整结果，可下载 Excel、CSV、变更记录、异常记录和 JSON 质量报告。</p>
          </li>
        </ol>
        <div class="upload-tips">
          <ShieldCheck :size="17" />
          <p>所有数据由本机服务保存。原始内容独立保留，清洗操作不会覆盖源数据。</p>
        </div>
        <footer>
          <button class="button primary" @click="helpOpen = false">
            开始使用<ArrowRight :size="15" />
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>
