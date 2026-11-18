<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DataCard, DrawerFocus, FlowStep, MaintenanceNote, RepoOverview, RoleBlock, Storyline } from '../api'

const props = defineProps<{
  overview: RepoOverview | null
  loading: boolean
  llmConfigured: boolean
  notes: MaintenanceNote[]
}>()

const emit = defineEmits<{
  inspect: [focus: DrawerFocus]
  generateAi: []
  openSettings: []
}>()

const activeRoleId = ref<string>('all')
const activeStoryId = ref<string>('')

watch(() => props.overview, val => {
  activeRoleId.value = 'all'
  activeStoryId.value = val?.storylines?.[0]?.id || ''
}, { immediate: true })

const activeStory = computed<Storyline | null>(() => {
  const list = props.overview?.storylines || []
  return list.find(s => s.id === activeStoryId.value) || list[0] || null
})

// Automatic 2-row layered layout for SVG topology based on out-degree vs in-degree
const graphLayout = computed(() => {
  const roles = props.overview?.roles || []
  const flows = props.overview?.roleFlows || []
  if (!roles.length) return { width: 920, height: 240, nodes: [], edges: [] }

  const outDeg: Record<string, number> = {}
  const inDeg: Record<string, number> = {}
  for (const r of roles) { outDeg[r.id] = 0; inDeg[r.id] = 0 }
  for (const f of flows) {
    outDeg[f.from] = (outDeg[f.from] || 0) + 1
    inDeg[f.to] = (inDeg[f.to] || 0) + 1
  }

  const sorted = [...roles].sort((a, b) => (outDeg[b.id] - inDeg[b.id]) - (outDeg[a.id] - inDeg[a.id]))
  const topCount = roles.length <= 3 ? roles.length : Math.max(1, Math.min(2, Math.ceil(roles.length / 3)))
  const topRow = sorted.slice(0, topCount)
  const bottomRow = sorted.slice(topCount)

  const width = 920
  const nodeW = 196
  const nodeH = 66
  const height = bottomRow.length ? 276 : 140

  const coords: Record<string, { x: number; y: number; role: RoleBlock }> = {}
  const placeRow = (items: RoleBlock[], y: number) => {
    const gap = (width - items.length * nodeW) / (items.length + 1)
    items.forEach((role, idx) => {
      coords[role.id] = { x: Math.round(gap + idx * (nodeW + gap)), y, role }
    })
  }
  placeRow(topRow, 24)
  if (bottomRow.length) placeRow(bottomRow, 184)

  const edges = flows.flatMap((f, idx) => {
    const src = coords[f.from]
    const dst = coords[f.to]
    if (!src || !dst) return []
    const sameRow = src.y === dst.y
    const leftToRight = src.x <= dst.x
    const x1 = sameRow ? (leftToRight ? src.x + nodeW : src.x) : src.x + nodeW / 2
    const y1 = sameRow ? src.y + Math.round(nodeH / 2) : src.y + nodeH
    const x2 = sameRow ? (leftToRight ? dst.x : dst.x + nodeW) : dst.x + nodeW / 2
    const y2 = sameRow ? dst.y + Math.round(nodeH / 2) : dst.y
    const path = sameRow
      ? `M ${x1} ${y1} L ${x2} ${y2}`
      : `M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`
    const lx = Math.round((x1 + x2) / 2)
    const ly = sameRow ? y1 - 8 : Math.round((y1 + y2) / 2) + (idx % 2 === 0 ? -9 : 11)
    const active = activeRoleId.value === 'all' || f.from === activeRoleId.value || f.to === activeRoleId.value
    return [{ key: `${f.from}-${f.to}-${idx}`, path, lx, ly, label: f.action, active }]
  })

  return {
    width,
    height,
    nodeW,
    nodeH,
    nodes: Object.values(coords).map(n => ({
      ...n,
      active: activeRoleId.value === 'all' || activeRoleId.value === n.role.id ||
        flows.some(f => (f.from === activeRoleId.value && f.to === n.role.id) || (f.to === activeRoleId.value && f.from === n.role.id)),
      selected: activeRoleId.value === n.role.id,
      notes: props.notes.filter(nt => !nt.resolved && nt.target_key === n.role.id).length,
    })),
    edges,
  }
})

function inspectRole(role: RoleBlock) {
  emit('inspect', {
    title: role.title,
    subtitle: role.subtitle,
    howPlain: role.plainHow,
    targetType: 'module',
    targetKey: role.id,
    revision: props.overview?.revision || 'HEAD',
    anchors: role.anchors,
  })
}

function inspectStep(story: Storyline, step: FlowStep) {
  emit('inspect', {
    title: `${story.title} · 步骤 ${step.stepNo}`,
    subtitle: step.what,
    howPlain: `${step.why}\n\n${step.howPlain}`,
    targetType: 'flow',
    targetKey: `${story.id}:step-${step.stepNo}`,
    revision: props.overview?.revision || 'HEAD',
    anchors: step.anchors,
  })
}

function inspectData(card: DataCard) {
  emit('inspect', {
    title: card.plainName,
    subtitle: card.purpose,
    howPlain: card.relations.length
      ? `${card.rawName}（${card.fieldCount} 字段）· ${card.relations.join('，')}`
      : `${card.rawName}（${card.fieldCount} 字段）`,
    targetType: 'symbol',
    targetKey: card.rawName,
    revision: props.overview?.revision || 'HEAD',
    anchors: card.anchors,
  })
}
</script>

<template>
  <div v-if="loading && !overview" class="card empty-box large">正在扫描仓库拓扑…</div>

  <div v-else-if="overview" class="stack-md">
    <section class="card summary-banner">
      <div class="summary-main">
        <div class="row-gap">
          <span class="badge">{{ overview.language.toUpperCase() }}</span>
          <code class="sha-chip">{{ overview.commit.slice(0, 8) }}</code>
          <span v-if="overview.sourceMode === 'llm'" class="badge badge-blue">AI · {{ overview.modelName }}</span>
        </div>
        <h2 class="summary-title">{{ overview.headline }}</h2>
        <p class="summary-desc">{{ overview.narrative }}</p>
      </div>

      <div class="summary-side">
        <div class="stat-pills">
          <div><span>文件</span><strong>{{ overview.stats.files }}</strong></div>
          <div><span>代码行</span><strong>{{ overview.stats.lines.toLocaleString() }}</strong></div>
          <div><span>模块</span><strong>{{ overview.roles.length }}</strong></div>
          <div><span>测试</span><strong>{{ overview.stats.testFiles }}</strong></div>
        </div>
        <button
          type="button"
          class="btn btn-sm"
          :disabled="loading"
          @click="llmConfigured ? emit('generateAi') : emit('openSettings')"
        >
          {{ loading ? '生成中…' : llmConfigured ? 'AI 重新提炼' : '配置 AI 密钥' }}
        </button>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <span class="card-title">模块分工与数据流向</span>
        <div class="row-gap">
          <button v-if="activeRoleId !== 'all'" type="button" class="btn btn-sm" @click="activeRoleId = 'all'">
            重置筛选
          </button>
        </div>
      </div>

      <div class="topology-wrap">
        <svg class="topology-svg" :viewBox="`0 0 ${graphLayout.width} ${graphLayout.height}`" role="img" aria-label="模块协作流向图">
          <defs>
            <marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0 1 L10 5 L0 9 Z" fill="#94a3b8" />
            </marker>
            <marker id="flow-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0 1 L10 5 L0 9 Z" fill="#2563eb" />
            </marker>
          </defs>

          <g v-for="edge in graphLayout.edges" :key="edge.key" :opacity="edge.active ? 1 : 0.22">
            <path
              :d="edge.path"
              fill="none"
              :stroke="edge.active && activeRoleId !== 'all' ? '#2563eb' : '#94a3b8'"
              :stroke-width="edge.active && activeRoleId !== 'all' ? 2 : 1.5"
              :marker-end="edge.active && activeRoleId !== 'all' ? 'url(#flow-arrow-active)' : 'url(#flow-arrow)'"
            />
            <text :x="edge.lx" :y="edge.ly" text-anchor="middle" class="svg-edge-label">{{ edge.label }}</text>
          </g>

          <g
            v-for="node in graphLayout.nodes"
            :key="node.role.id"
            class="svg-node"
            :class="{ selected: node.selected, dimmed: !node.active }"
            tabindex="0"
            role="button"
            @click="activeRoleId = activeRoleId === node.role.id ? 'all' : node.role.id"
          >
            <rect :x="node.x" :y="node.y" :width="graphLayout.nodeW" :height="graphLayout.nodeH" rx="8" />
            <text :x="node.x + 14" :y="node.y + 26" class="svg-node-title">{{ node.role.title }}</text>
            <text :x="node.x + 14" :y="node.y + 47" class="svg-node-meta">
              {{ node.role.fileCount }} 文件 · {{ node.role.lineCount.toLocaleString() }} 行{{ node.notes ? ` · ${node.notes} 便签` : '' }}
            </text>
          </g>
        </svg>
      </div>

      <div class="role-strip">
        <div
          v-for="role in overview.roles"
          :key="role.id"
          class="role-mini"
          :class="{ active: activeRoleId === role.id }"
          @click="inspectRole(role)"
        >
          <div class="row-between">
            <strong>{{ role.title }}</strong>
            <span class="arrow-hint">详情 →</span>
          </div>
          <p>{{ role.subtitle }}</p>
        </div>
      </div>
    </section>

    <section v-if="overview.storylines.length" class="card">
      <div class="card-head">
        <span class="card-title">核心运行链路</span>
        <div class="pill-group">
          <button
            v-for="st in overview.storylines"
            :key="st.id"
            type="button"
            class="tab-pill"
            :class="{ active: activeStory?.id === st.id }"
            @click="activeStoryId = st.id"
          >
            {{ st.title }}
          </button>
        </div>
      </div>

      <div v-if="activeStory" class="pipeline-body">
        <div class="pipeline-track">
          <button
            v-for="step in activeStory.steps"
            :key="step.stepNo"
            type="button"
            class="pipeline-step"
            @click="inspectStep(activeStory, step)"
          >
            <span class="step-idx">{{ String(step.stepNo).padStart(2, '0') }}</span>
            <strong>{{ step.what }}</strong>
            <p>{{ step.why }}</p>
          </button>
        </div>
      </div>
    </section>

    <section v-if="overview.dataCards.length" class="card">
      <div class="card-head">
        <span class="card-title">数据模型 ({{ overview.dataCards.length }})</span>
      </div>
      <div class="schema-grid">
        <button
          v-for="dc in overview.dataCards"
          :key="dc.id"
          type="button"
          class="schema-card"
          @click="inspectData(dc)"
        >
          <div class="row-between">
            <strong>{{ dc.plainName }}</strong>
            <span class="muted">{{ dc.fieldCount }} 字段</span>
          </div>
          <code>{{ dc.rawName }}</code>
          <span v-if="dc.relations.length" class="schema-rel">{{ dc.relations[0] }}</span>
        </button>
      </div>
    </section>
  </div>
</template>
