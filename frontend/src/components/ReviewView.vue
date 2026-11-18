<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import {
  api, type AnalysisDetail, type AnalysisSummary, type Anchor,
  type Commit, type DrawerFocus, type FlowComparison, type FlowStep,
} from '../api'

const props = defineProps<{
  projectId: number
  isDeveloper: boolean
  isReviewer: boolean
  llmConfigured: boolean
  commits: Commit[]
  analyses: AnalysisSummary[]
  presetCompare?: { base: string; head: string; title: string } | null
}>()

const emit = defineEmits<{
  inspect: [focus: DrawerFocus]
  openAnchor: [anchor: Anchor, revision: string]
  analysesChanged: []
  openSettings: []
  presetConsumed: []
}>()

const showForm = ref(false)
const busy = ref(false)
const localError = ref('')
const current = ref<AnalysisDetail | null>(null)
const selectedFlowIdx = ref(0)

const form = reactive({
  task_type: 'commit_compare' as 'commit_compare' | 'ai_change',
  title: '审阅工作区变更',
  user_prompt: '',
  raw_log: '',
  base_ref: 'HEAD',
  head_ref: 'WORKTREE',
  use_llm: false,
})

const reviewForm = reactive({
  verdict: 'approved' as 'approved' | 'attention' | 'needs_work',
  comment: '',
  test_status: 'not_run' as 'not_run' | 'passed' | 'failed' | 'blocked',
  test_notes: '',
})

function quickPreset(kind: 'worktree' | 'latest_commit') {
  showForm.value = true
  if (kind === 'worktree') {
    form.task_type = 'commit_compare'
    form.title = '审阅未提交改动'
    form.base_ref = 'HEAD'
    form.head_ref = 'WORKTREE'
  } else {
    form.task_type = 'commit_compare'
    form.title = props.commits[0]?.subject || '对比最近提交'
    form.base_ref = props.commits[1]?.sha || 'HEAD~1'
    form.head_ref = props.commits[0]?.sha || 'HEAD'
  }
}

async function openAnalysis(taskId: number) {
  busy.value = true; localError.value = ''
  try {
    current.value = await api<AnalysisDetail>(`/projects/${props.projectId}/analyses/${taskId}`)
    selectedFlowIdx.value = 0
  } catch (err) {
    localError.value = err instanceof Error ? err.message : '读取报告失败'
  } finally {
    busy.value = false
  }
}

watch(() => props.presetCompare, async preset => {
  if (!preset) return
  form.task_type = 'commit_compare'
  form.base_ref = preset.base
  form.head_ref = preset.head
  form.title = preset.title
  emit('presetConsumed')
  await runAnalysis()
}, { immediate: true })

watch(() => props.analyses, list => {
  if (list.length && (!current.value || current.value.project_id !== props.projectId)) {
    openAnalysis(list[0].id)
  } else if (!list.length) {
    current.value = null
  }
}, { immediate: true })

async function runAnalysis() {
  busy.value = true; localError.value = ''
  try {
    const created = await api<AnalysisDetail>(`/projects/${props.projectId}/analyses`, 'POST', form)
    current.value = created
    selectedFlowIdx.value = 0
    showForm.value = false
    emit('analysesChanged')
  } catch (err) {
    localError.value = err instanceof Error ? err.message : '分析失败'
  } finally {
    busy.value = false
  }
}

async function explainWithAi() {
  if (!current.value) return
  if (!props.llmConfigured) { emit('openSettings'); return }
  busy.value = true; localError.value = ''
  try {
    current.value = await api<AnalysisDetail>(
      `/projects/${props.projectId}/analyses/${current.value.id}/explain`, 'POST',
    )
    emit('analysesChanged')
  } catch (err) {
    localError.value = err instanceof Error ? err.message : 'AI 解读失败'
  } finally {
    busy.value = false
  }
}

async function submitReview() {
  if (!current.value) return
  busy.value = true; localError.value = ''
  try {
    await api(`/projects/${props.projectId}/analyses/${current.value.id}/reviews`, 'POST', reviewForm)
    reviewForm.comment = ''
    reviewForm.test_notes = ''
    await openAnalysis(current.value.id)
    emit('analysesChanged')
  } catch (err) {
    localError.value = err instanceof Error ? err.message : '提交失败'
  } finally {
    busy.value = false
  }
}

function inspectFlowStep(fc: FlowComparison, step: FlowStep, side: 'before' | 'after') {
  if (!current.value) return
  emit('inspect', {
    title: `${fc.plainTitle} · ${side === 'before' ? '旧' : '新'}步骤 ${step.stepNo}`,
    subtitle: step.what,
    howPlain: `${step.why}\n\n${step.howPlain}`,
    targetType: 'flow',
    targetKey: fc.path,
    revision: side === 'before' ? current.value.base_sha : current.value.head_sha,
    anchors: step.anchors,
  })
}

const verdictLabel: Record<string, string> = {
  approved: '通过', attention: '需关注', needs_work: '需修改',
}
const testLabel: Record<string, string> = {
  not_run: '未测', passed: '测试通过', failed: '未通过', blocked: '受阻',
}
</script>

<template>
  <div class="stack-md">
    <div v-if="localError" class="alert-bar err">{{ localError }}</div>

    <section class="card">
      <div class="card-head">
        <div class="row-gap">
          <span class="card-title">版本影响对比</span>
          <div v-if="analyses.length" class="pill-group">
            <button
              v-for="item in analyses.slice(0, 6)"
              :key="item.id"
              type="button"
              class="tab-pill"
              :class="{ active: current?.id === item.id }"
              @click="openAnalysis(item.id)"
            >
              {{ item.title }}
              <span class="muted">({{ item.latest_verdict ? verdictLabel[item.latest_verdict] : '待审' }})</span>
            </button>
          </div>
        </div>

        <div v-if="isDeveloper" class="row-gap">
          <button type="button" class="btn btn-sm" @click="quickPreset('worktree')">对比工作区</button>
          <button type="button" class="btn btn-sm" @click="quickPreset('latest_commit')">对比最近提交</button>
          <button type="button" class="btn btn-primary btn-sm" @click="showForm = !showForm">
            {{ showForm ? '收起' : '新建对比' }}
          </button>
        </div>
      </div>

      <form v-if="showForm && isDeveloper" class="form-panel" @submit.prevent="runAnalysis">
        <div class="grid-4">
          <label>
            类型
            <select v-model="form.task_type" name="taskType">
              <option value="commit_compare">Git 比较</option>
              <option value="ai_change">AI 任务记录</option>
            </select>
          </label>
          <label>
            标题
            <input v-model="form.title" name="analysisTitle" required />
          </label>
          <label>
            基准 (Base)
            <input v-model="form.base_ref" name="baseRef" list="commitRefs" required />
          </label>
          <label>
            目标 (Head)
            <input v-model="form.head_ref" name="headRef" list="commitRefs" required />
          </label>
          <datalist id="commitRefs">
            <option value="WORKTREE">WORKTREE</option>
            <option value="HEAD">HEAD</option>
            <option value="HEAD~1">HEAD~1</option>
            <option v-for="c in commits" :key="c.sha" :value="c.sha">{{ c.short_sha }} · {{ c.subject }}</option>
          </datalist>
          <label class="span-all">
            {{ form.task_type === 'ai_change' ? '修改要求（必填）' : '备注说明（可选）' }}
            <input v-model="form.user_prompt" name="userPrompt" :required="form.task_type === 'ai_change'" placeholder="修改背景或 AI 任务提示词" />
          </label>
        </div>
        <div class="row-between">
          <label class="check-inline">
            <input v-model="form.use_llm" type="checkbox" name="useLlm" />
            <span>同步调用 AI 解读</span>
          </label>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="busy">
            {{ busy ? '分析中…' : '开始对比' }}
          </button>
        </div>
      </form>

      <div v-if="!analyses.length && !showForm" class="empty-box">
        {{ isDeveloper ? '点击「对比工作区」或「新建对比」生成变更影响分析' : '暂无对比记录' }}
      </div>
    </section>

    <template v-if="current">
      <section class="card summary-banner">
        <div class="summary-main">
          <div class="row-gap">
            <code class="sha-chip">{{ current.base_sha.slice(0, 7) }}</code>
            <span class="muted">→</span>
            <code class="sha-chip">{{ current.head_sha === 'WORKTREE' ? 'WORKTREE' : current.head_sha.slice(0, 7) }}</code>
            <span v-if="current.llm_status === 'generated'" class="badge badge-blue">AI · {{ current.result.plainSummary.model }}</span>
          </div>
          <h2 class="summary-title">{{ current.result.plainSummary.headline }}</h2>
          <p class="summary-desc">{{ current.result.plainSummary.beforeVsAfter }}</p>

          <div v-if="current.result.plainSummary.riskPoints.length" class="risk-compact">
            <div v-for="(rp, idx) in current.result.plainSummary.riskPoints" :key="idx" class="risk-row">
              <div><strong>{{ rp.title }}：</strong>{{ rp.detail }}</div>
              <button
                v-for="(anc, aIdx) in rp.anchors || []"
                :key="aIdx"
                type="button"
                class="code-chip"
                @click="emit('openAnchor', anc, current.head_sha)"
              >
                {{ anc.path.split('/').pop() }}:L{{ anc.line }}
              </button>
            </div>
          </div>
        </div>

        <div class="summary-side">
          <div class="stat-pills">
            <div><span>变更文件</span><strong>{{ current.result.diagnostics.changedFileCount }}</strong></div>
            <div><span>变更流程</span><strong>{{ current.result.diagnostics.changedFlowCount }}</strong></div>
            <div><span>波及调用</span><strong>{{ current.result.diagnostics.impactCount }}</strong></div>
          </div>
          <button
            v-if="current.result.diagnostics.changedFileCount > 0"
            type="button"
            class="btn btn-sm"
            :disabled="busy"
            @click="explainWithAi"
          >
            {{ llmConfigured ? 'AI 深度解读' : '配置 AI 密钥' }}
          </button>
        </div>
      </section>

      <section v-if="current.result.flowComparisons.length" class="card">
        <div class="card-head">
          <span class="card-title">流程前后对照</span>
          <div class="pill-group">
            <button
              v-for="(fc, idx) in current.result.flowComparisons"
              :key="fc.id"
              type="button"
              class="tab-pill"
              :class="{ active: selectedFlowIdx === idx }"
              @click="selectedFlowIdx = idx"
            >
              {{ fc.plainTitle }}
            </button>
          </div>
        </div>

        <div v-if="current.result.flowComparisons[selectedFlowIdx]" class="diff-cols">
          <div class="diff-col">
            <div class="diff-col-head old">变更前 ({{ current.base_sha.slice(0, 7) }})</div>
            <button
              v-for="st in current.result.flowComparisons[selectedFlowIdx].beforeSteps"
              :key="'b-' + st.stepNo"
              type="button"
              class="step-diff-card"
              :class="st.changeTag === 'modified' || st.changeTag === 'deleted' ? 'is-old-mod' : ''"
              @click="inspectFlowStep(current.result.flowComparisons[selectedFlowIdx], st, 'before')"
            >
              <div class="row-between">
                <span class="step-idx">{{ String(st.stepNo).padStart(2, '0') }}</span>
                <span v-if="st.changeTag !== 'unchanged'" class="badge badge-red">
                  {{ st.changeTag === 'deleted' ? '移除' : '修改' }}
                </span>
              </div>
              <strong>{{ st.what }}</strong>
            </button>
          </div>

          <div class="diff-col">
            <div class="diff-col-head new">变更后 ({{ current.head_sha === 'WORKTREE' ? 'WORKTREE' : current.head_sha.slice(0, 7) }})</div>
            <button
              v-for="st in current.result.flowComparisons[selectedFlowIdx].afterSteps"
              :key="'a-' + st.stepNo"
              type="button"
              class="step-diff-card"
              :class="st.changeTag === 'added' ? 'is-new-add' : st.changeTag === 'modified' ? 'is-new-mod' : ''"
              @click="inspectFlowStep(current.result.flowComparisons[selectedFlowIdx], st, 'after')"
            >
              <div class="row-between">
                <span class="step-idx">{{ String(st.stepNo).padStart(2, '0') }}</span>
                <span v-if="st.changeTag !== 'unchanged'" class="badge" :class="st.changeTag === 'added' ? 'badge-green' : 'badge-amber'">
                  {{ st.changeTag === 'added' ? '新增' : '修改' }}
                </span>
              </div>
              <strong>{{ st.what }}</strong>
            </button>
          </div>
        </div>
      </section>

      <div class="split-2">
        <section class="card">
          <div class="card-head">
            <span class="card-title">波及调用链 ({{ current.result.impactRadius.length }})</span>
          </div>
          <div v-if="!current.result.impactRadius.length" class="empty-box">无外部上游函数直接依赖此变更</div>
          <div v-else class="compact-list">
            <div v-for="imp in current.result.impactRadius" :key="imp.id" class="compact-row">
              <div>
                <div class="row-gap">
                  <strong>{{ imp.plainName }}</strong>
                  <span class="badge">{{ imp.distance === 1 ? '直接' : `${imp.distance} 跳` }}</span>
                </div>
                <small class="muted">{{ imp.chain }}</small>
              </div>
              <button type="button" class="code-chip" @click="emit('openAnchor', imp.anchor, current.head_sha)">
                {{ imp.anchor.path.split('/').pop() }}:L{{ imp.anchor.line }}
              </button>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">审阅签核 ({{ current.reviews.length }})</span>
          </div>

          <form v-if="isReviewer" class="form-panel" @submit.prevent="submitReview">
            <div class="grid-2">
              <label>
                结论
                <select v-model="reviewForm.verdict" name="reviewVerdict">
                  <option value="approved">通过</option>
                  <option value="attention">需关注</option>
                  <option value="needs_work">需修改</option>
                </select>
              </label>
              <label>
                测试状态
                <select v-model="reviewForm.test_status" name="testStatus">
                  <option value="not_run">未执行</option>
                  <option value="passed">通过</option>
                  <option value="failed">未通过</option>
                  <option value="blocked">受阻</option>
                </select>
              </label>
              <label class="span-all">
                审阅意见
                <input v-model="reviewForm.comment" name="reviewComment" required placeholder="输入核对意见" />
              </label>
              <label v-if="reviewForm.test_status !== 'not_run'" class="span-all">
                测试说明
                <input v-model="reviewForm.test_notes" name="testNotes" required placeholder="命令或验证结果" />
              </label>
            </div>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="busy">提交审阅</button>
          </form>

          <div v-if="!current.reviews.length" class="empty-box">暂无签核记录</div>
          <div v-else class="compact-list">
            <div v-for="rev in current.reviews" :key="rev.id" class="compact-row">
              <div>
                <div class="row-gap">
                  <strong>{{ verdictLabel[rev.verdict] || rev.verdict }}</strong>
                  <span class="badge">{{ testLabel[rev.test_status] || rev.test_status }}</span>
                  <span class="muted">{{ rev.author_username }}</span>
                </div>
                <p class="row-text">{{ rev.comment }}</p>
                <small v-if="rev.test_notes" class="muted">{{ rev.test_notes }}</small>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
