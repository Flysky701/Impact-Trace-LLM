<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type Anchor, type AskResponse, type DrawerFocus, type MaintenanceNote } from '../api'

const props = defineProps<{
  projectId: number
  focus: DrawerFocus
  notes: MaintenanceNote[]
}>()

const emit = defineEmits<{
  close: []
  openAnchor: [anchor: Anchor, revision: string]
  noteCreated: [note: MaintenanceNote]
}>()

const matchedNotes = computed(() =>
  props.notes.filter(n => !n.resolved && (
    n.target_key === props.focus.targetKey ||
    props.focus.anchors.some(a => a.path === n.target_key)
  ))
)

const question = ref('')
const asking = ref(false)
const askError = ref('')
const reply = ref<AskResponse | null>(null)

const showNoteForm = ref(false)
const savingNote = ref(false)
const noteForm = reactive({
  kind: 'pitfall' as 'pitfall' | 'refactor' | 'note',
  title: '',
  content: '',
})

watch(() => props.focus, () => {
  question.value = ''
  askError.value = ''
  reply.value = null
  showNoteForm.value = false
})

const quickPrompts = [
  '中途报错或取消会发生什么？',
  '哪些上游环节依赖这里？',
  '改动这里最需注意什么？',
]

async function ask(preset?: string) {
  const q = (preset || question.value).trim()
  if (!q) return
  question.value = q
  asking.value = true; askError.value = ''
  const primary = props.focus.anchors[0]
  try {
    reply.value = await api<AskResponse>(`/projects/${props.projectId}/ask`, 'POST', {
      question: q,
      revision: props.focus.revision || 'HEAD',
      target_path: primary?.path || '',
      target_line: primary?.line || 0,
      target_label: props.focus.title,
    })
  } catch (err) {
    askError.value = err instanceof Error ? err.message : '提问失败'
  } finally {
    asking.value = false
  }
}

async function submitNote() {
  if (!noteForm.title.trim() || !noteForm.content.trim()) return
  savingNote.value = true
  try {
    const created = await api<MaintenanceNote>(`/projects/${props.projectId}/notes`, 'POST', {
      target_type: props.focus.targetType,
      target_key: props.focus.targetKey,
      target_label: props.focus.title,
      kind: noteForm.kind,
      title: noteForm.title,
      content: noteForm.content,
    })
    noteForm.title = ''; noteForm.content = ''
    showNoteForm.value = false
    emit('noteCreated', created)
  } catch (err) {
    askError.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    savingNote.value = false
  }
}
</script>

<template>
  <aside class="inspector-drawer" aria-label="代码与上下文面板">
    <div class="drawer-top">
      <div>
        <h3>{{ focus.title }}</h3>
        <span class="muted">{{ focus.subtitle }}</span>
      </div>
      <button type="button" class="icon-close" aria-label="关闭详情抽屉" @click="emit('close')">✕</button>
    </div>

    <div class="drawer-body">
      <section class="drawer-block">
        <div class="block-label">实现说明</div>
        <p class="drawer-text">{{ focus.howPlain }}</p>

        <div v-if="focus.anchors.length" class="row-gap">
          <button
            v-for="(anc, idx) in focus.anchors"
            :key="idx"
            type="button"
            class="code-chip"
            @click="emit('openAnchor', anc, focus.revision)"
          >
            {{ anc.path.split('/').pop() }}:L{{ anc.line }}{{ anc.end && anc.end !== anc.line ? `–${anc.end}` : '' }}
          </button>
        </div>
      </section>

      <section class="drawer-block">
        <div class="row-between">
          <span class="block-label">关联便签 ({{ matchedNotes.length }})</span>
          <button type="button" class="btn btn-sm" @click="showNoteForm = !showNoteForm">
            {{ showNoteForm ? '收起' : '+ 便签' }}
          </button>
        </div>

        <form v-if="showNoteForm" class="stack-sm" style="margin-top: 8px" @submit.prevent="submitNote">
          <select v-model="noteForm.kind" name="noteKind">
            <option value="pitfall">避坑</option>
            <option value="refactor">重构</option>
            <option value="note">备注</option>
          </select>
          <input v-model="noteForm.title" name="noteTitle" required placeholder="便签标题" />
          <textarea v-model="noteForm.content" name="noteContent" rows="2" required placeholder="具体注意事项"></textarea>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="savingNote">保存</button>
        </form>

        <div v-for="note in matchedNotes" :key="note.id" class="drawer-note">
          <strong>{{ note.title }}</strong>
          <p>{{ note.content }}</p>
        </div>
      </section>

      <section class="drawer-block">
        <div class="block-label">上下文追问</div>
        <div class="prompt-chips">
          <button
            v-for="qp in quickPrompts"
            :key="qp"
            type="button"
            class="chip-btn"
            :disabled="asking"
            @click="ask(qp)"
          >
            {{ qp }}
          </button>
        </div>
        <form class="ask-inline" @submit.prevent="ask()">
          <input v-model="question" name="drawerQuestion" placeholder="提问此模块或步骤…" />
          <button type="submit" class="btn btn-primary btn-sm" :disabled="asking || !question.trim()">
            {{ asking ? '…' : '提问' }}
          </button>
        </form>

        <div v-if="askError" class="alert-bar err" style="margin-top: 8px">{{ askError }}</div>

        <div v-if="reply" class="qa-answer">
          <p>{{ reply.answer }}</p>
          <ul v-if="reply.keyPoints.length">
            <li v-for="(pt, idx) in reply.keyPoints" :key="idx">{{ pt }}</li>
          </ul>
          <div v-if="reply.anchors.length" class="row-gap">
            <button
              v-for="(anc, idx) in reply.anchors"
              :key="idx"
              type="button"
              class="code-chip"
              @click="emit('openAnchor', anc, focus.revision)"
            >
              {{ anc.path.split('/').pop() }}:L{{ anc.line }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </aside>
</template>
