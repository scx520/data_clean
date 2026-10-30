<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Search, X } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string[]
  fields: string[]
  disabled?: boolean
  emptyMeansAll?: boolean
  maxFields?: number
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const query = ref('')
const error = ref('')
const filtered = computed(() =>
  props.fields.filter((field) =>
    field.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase()),
  ),
)
const selected = computed(() => new Set(props.modelValue))

function update(next: string[]) {
  if (props.disabled) return
  if (props.maxFields && next.length > props.maxFields) {
    error.value = `此规则最多选择 ${props.maxFields} 个字段，请先搜索缩小范围。`
    return
  }
  error.value = ''
  emit('update:modelValue', next)
}
function toggle(field: string) {
  update(
    selected.value.has(field)
      ? props.modelValue.filter((value) => value !== field)
      : [...props.modelValue, field],
  )
}
function clearQuery() {
  query.value = ''
  error.value = ''
}
function batch(action: 'select' | 'clear' | 'invert') {
  const scope = new Set(filtered.value)
  const next = new Set(props.modelValue)
  for (const field of scope) {
    if (action === 'select' || (action === 'invert' && !selected.value.has(field))) next.add(field)
    else next.delete(field)
  }
  update(props.fields.filter((field) => next.has(field)))
}
</script>

<template>
  <div class="field-selector">
    <label class="field-search"
      ><Search :size="13" /><input
        v-model="query"
        :disabled="disabled"
        placeholder="搜索字段名称…"
        aria-label="搜索字段" /><button
        v-if="query"
        class="icon-button small"
        :disabled="disabled"
        aria-label="清除字段搜索"
        @click="clearQuery"
      >
        <X :size="12" /></button
    ></label>
    <div class="field-selection-tools">
      <button :disabled="disabled || !filtered.length" @click="batch('select')">
        {{ query.trim() ? '全选匹配项' : '全选' }}</button
      ><button
        :disabled="disabled || !filtered.some((field) => selected.has(field))"
        @click="batch('clear')"
      >
        {{ query.trim() ? '清空匹配项' : '清空选择' }}</button
      ><button :disabled="disabled || !filtered.length" @click="batch('invert')">
        {{ query.trim() ? '反选匹配项' : '反选' }}</button
      ><span>{{ query.trim() ? `匹配 ${filtered.length} 项` : `共 ${fields.length} 项` }}</span>
    </div>
    <div class="field-chips">
      <button
        v-for="field in filtered"
        :key="field"
        :disabled="disabled"
        :class="['field-chip', { chosen: selected.has(field) }]"
        :aria-pressed="selected.has(field)"
        @click="toggle(field)"
      >
        <Check v-if="selected.has(field)" :size="11" />{{ field }}</button
      ><span v-if="!fields.length" class="field-empty">导入数据后选择字段</span
      ><span v-else-if="!filtered.length" class="field-empty">没有匹配字段，试试其他关键词。</span>
    </div>
    <p class="field-selection-summary" aria-live="polite">
      {{
        modelValue.length
          ? `已选 ${modelValue.length} 个字段${maxFields ? `，最多 ${maxFields} 个` : ''}`
          : emptyMeansAll
            ? `未单独指定，当前使用全部 ${fields.length} 个字段`
            : '尚未选择字段，请至少选择一个'
      }}<span v-if="query.trim()">搜索仅筛选字段列表，不改变已有选择。</span>
    </p>
    <p v-if="error" class="field-selection-error" role="alert">{{ error }}</p>
  </div>
</template>
