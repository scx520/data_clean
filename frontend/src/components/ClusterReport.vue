<script setup lang="ts">
import { Sparkles, Users } from 'lucide-vue-next'
import type { ClusterAnalysis } from '../types'
defineProps<{ analyses: ClusterAnalysis[] }>()
const count = (value: number) => value.toLocaleString('zh-CN')
</script>

<template>
  <section v-for="analysis in analyses" :key="analysis.rule_index" class="cluster-report">
    <div class="cluster-report-heading">
      <Sparkles :size="17" />
      <h3>
        {{ analysis.output }} · {{ analysis.mode === 'numeric' ? '数值聚类' : '中文文本聚类' }}
      </h3>
      <span>{{ analysis.clusters }} 组</span>
    </div>
    <p class="cluster-fields">分析字段：{{ analysis.fields.join('、') }}</p>
    <div class="cluster-totals">
      <span><Users :size="14" />参与 {{ count(analysis.participating_rows) }} 行</span
      ><span>未参与 {{ count(analysis.excluded_rows) }} 行</span>
    </div>
    <div class="cluster-groups">
      <article v-for="group in analysis.groups" :key="group.label" class="cluster-group">
        <header>
          <strong>{{ group.label }}</strong
          ><span>{{ count(group.count) }} 行 · {{ group.share }}%</span>
        </header>
        <div class="cluster-bar"><i :style="{ width: `${group.share}%` }"></i></div>
        <div v-if="group.means" class="cluster-means">
          <span v-for="(value, field) in group.means" :key="field"
            >{{ field }}均值
            <b>{{ value.toLocaleString('zh-CN', { maximumFractionDigits: 4 }) }}</b></span
          >
        </div>
        <div v-if="group.keywords?.length" class="cluster-keywords">
          <span v-for="word in group.keywords" :key="word">{{ word }}</span>
        </div>
        <p v-for="(example, i) in group.examples" :key="i" class="cluster-example">
          示例：{{ example }}
        </p>
      </article>
    </div>
    <p class="cluster-note">
      {{
        analysis.note
      }}
      分组基于此规则执行时的数据快照，后续规则可能继续处理记录。新增标签不参与完整性评分。
    </p>
  </section>
</template>
