<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { api, type Anchor, type AskResponse, type DrawerFocus, type Hotspot, type MaintenanceNote, type RoleBlock } from '../api'

const props = defineProps<{
  projectId: number
  revision: string
  roles: RoleBlock[]
  hotspots: Hotspot[]
  notes: MaintenanceNote[]
}>()

const emit = defineEmits<{
  inspect: [focus: DrawerFocus]
  openAnchor: [anchor: Anchor, revision: string]
  notesChanged: []
}>()

const onlyOpen = ref(true)
const showCreate = ref(false)
const saving = ref(false)
const formError = ref('')

const noteForm = reactive({
  target_type: 'module' as 'module' | 'flow' | 'file' | 'symbol',
  target_key: props.roles[0]?.id || 'app',
  target_label: props.roles[0]?.title || '全局',
  kind: 'pitfall' as 'pitfall' | 'refactor' | 'note',
  title: '',
  content: '',
})

function onRoleChange(roleId: string) {
  noteForm.target_key = roleId
  const found = props.roles.find(r => r.id === roleId)
  noteForm.target_label = found ? found.title : roleId
}

const visibleNotes = computed(() =>
  onlyOpen.value ? props.notes.filter(n => !n.resolved) : props.notes
)

const repoQuestion = ref('')
const asking = ref(false)
const repoReply = ref<AskResponse | null>(null)

const repoPrompts = [
  '新增功能或页面应从哪几个模块入手？',
  '哪块逻辑耦合最重、修改时最易出错？',
  '核心数据从读入到落盘经过哪几步？',
]

async function askRepo(preset?: string) {
  const q = (preset || repoQuestion.value).trim()
  if (!q) return
  repoQuestion.value = q
  asking.value = true; formError.value = ''
  try {
    repoReply.value = await api<AskResponse>(`/projects/${props.projectId}/ask`, 'POST', {
      question: q,
      revision: props.revision || 'HEAD',
    })
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '提问失败'
  } finally {
    asking.value = false
  }
}

async function createNote() {
  saving.value = true; formError.value = ''
  try {
    await api(`/projects/${props.projectId}/notes`, 'POST', noteForm)
    noteForm.title = ''; noteForm.content = ''
    showCreate.value = false
    emit('notesChanged')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleNote(note: MaintenanceNote) {
  try {
    await api(`/projects/${props.projectId}/notes/${note.id}`, 'PATCH', { resolved: !note.resolved })
    emit('notesChanged')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '更新失败'
  }
}

async function removeNote(note: MaintenanceNote) {
  try {
    await api(`/projects/${props.projectId}/notes/${note.id}`, 'DELETE')
    emit('notesChanged')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '删除失败'
  }
}

function inspectHotspot(hp: Hotspot) {
  emit('inspect', {
    title: hp.title,
    subtitle: hp.metrics,
    howPlain: `${hp.whyHard}\n\n建议：${hp.splitIdea}`,
    targetType: 'symbol',
    targetKey: hp.anchors[0]?.path || hp.id,
    revision: props.revision || 'HEAD',
    anchors: hp.anchors,
  })
}
</script>

<template>
  <div class="stack-md">
    <div v-if="formError" class="alert-bar err">{{ formError }}</div>

    <div class="split-2">
      <section class="card">
        <div class="card-head">
          <span class="card-title">仓库问答</span>
        </div>
        <div class="pad-md">
          <div class="prompt-chips">
            <button
              v-for="p in repoPrompts"
              :key="p"
              type="button"
              class="chip-btn"
              :disabled="asking"
              @click="askRepo(p)"
            >
              {{ p }}
            </button>
          </div>
          <form class="ask-inline" @submit.prevent="askRepo()">
            <input v-model="repoQuestion" name="repoQuestion" placeholder="提问代码逻辑、架构流向或修改位置…" />
            <button type="submit" class="btn btn-primary" :disabled="asking || !repoQuestion.trim()">
              {{ asking ? '检索中…' : '提问' }}
            </button>
          </form>

          <div v-if="repoReply" class="qa-answer">
            <div class="row-gap">
              <span class="badge" :class="repoReply.mode === 'llm' ? 'badge-blue' : ''">
                {{ repoReply.mode === 'llm' ? `AI · ${repoReply.model}` : '静态索引' }}
              </span>
            </div>
            <p>{{ repoReply.answer }}</p>
            <ul v-if="repoReply.keyPoints.length">
              <li v-for="(pt, i) in repoReply.keyPoints" :key="i">{{ pt }}</li>
            </ul>
            <div v-if="repoReply.anchors.length" class="row-gap">
              <button
                v-for="(anc, i) in repoReply.anchors"
                :key="i"
                type="button"
                class="code-chip"
                @click="emit('openAnchor', anc, revision || 'HEAD')"
              >
                {{ anc.path.split('/').pop() }}:L{{ anc.line }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <span class="card-title">维护便签 ({{ visibleNotes.length }})</span>
          <div class="row-gap">
            <button type="button" class="btn btn-sm" @click="onlyOpen = !onlyOpen">
              {{ onlyOpen ? '全部' : '未处理' }}
            </button>
            <button type="button" class="btn btn-primary btn-sm" @click="showCreate = !showCreate">
              {{ showCreate ? '收起' : '新建' }}
            </button>
          </div>
        </div>

        <form v-if="showCreate" class="form-panel" @submit.prevent="createNote">
          <div class="grid-2">
            <label>
              关联模块
              <select :value="noteForm.target_key" name="noteModule" @change="onRoleChange(($event.target as HTMLSelectElement).value)">
                <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.title }}</option>
                <option value="global">全局</option>
              </select>
            </label>
            <label>
              分类
              <select v-model="noteForm.kind" name="noteKindMain">
                <option value="pitfall">避坑</option>
                <option value="refactor">重构</option>
                <option value="note">备忘</option>
              </select>
            </label>
            <label class="span-all">
              标题
              <input v-model="noteForm.title" name="noteTitleMain" required />
            </label>
            <label class="span-all">
              内容
              <textarea v-model="noteForm.content" name="noteContentMain" rows="2" required></textarea>
            </label>
          </div>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">保存便签</button>
        </form>

        <div v-if="!visibleNotes.length" class="empty-box">暂无维护便签</div>
        <div v-else class="compact-list">
          <div v-for="note in visibleNotes" :key="note.id" class="compact-row" :class="{ muted: note.resolved }">
            <div>
              <div class="row-gap">
                <span class="badge" :class="note.kind === 'pitfall' ? 'badge-amber' : ''">{{ note.target_label }}</span>
                <strong>{{ note.title }}</strong>
              </div>
              <p class="row-text">{{ note.content }}</p>
            </div>
            <div class="row-gap">
              <button type="button" class="btn btn-sm" @click="toggleNote(note)">
                {{ note.resolved ? '重开' : '完成' }}
              </button>
              <button type="button" class="btn btn-sm" @click="removeNote(note)">删除</button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section v-if="hotspots.length" class="card">
      <div class="card-head">
        <span class="card-title">复杂度热点 ({{ hotspots.length }})</span>
      </div>
      <div class="compact-list">
        <div v-for="hp in hotspots" :key="hp.id" class="compact-row">
          <div>
            <div class="row-gap">
              <span class="badge" :class="hp.severity === 'high' ? 'badge-red' : 'badge-amber'">{{ hp.metrics }}</span>
              <strong>{{ hp.title }}</strong>
            </div>
            <p class="row-text">{{ hp.splitIdea }}</p>
          </div>
          <button type="button" class="btn btn-sm" @click="inspectHotspot(hp)">查看实现 →</button>
        </div>
      </div>
    </section>
  </div>
</template>
