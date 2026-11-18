<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type Commit, type CommitDetail, type GitStatus } from '../api'

const props = defineProps<{
  projectId: number
  isDeveloper: boolean
  gitStatus: GitStatus | null
  commits: Commit[]
  totalCommits: number
  offset: number
}>()

const emit = defineEmits<{
  statusChanged: []
  committed: []
  paginate: [delta: number]
  openSource: [path: string, rev: string]
  reviewRefs: [baseRef: string, headRef: string, title: string]
  error: [err: unknown]
}>()

const paneMode = ref<'changes' | 'commits'>('changes')
const commitMessage = ref('')
const busy = ref(false)

const selectedFile = ref<{ path: string; staged: boolean } | null>(null)
const fileDiffText = ref('')
const selectedCommit = ref<CommitDetail | null>(null)

const unstagedAll = computed(() => [
  ...(props.gitStatus?.unstaged || []),
  ...(props.gitStatus?.untracked || []),
])

const changeCount = computed(() =>
  (props.gitStatus?.staged.length || 0) + unstagedAll.value.length
)

async function loadWorktreeDiff(path: string, staged: boolean) {
  selectedFile.value = { path, staged }
  selectedCommit.value = null
  try {
    const res = await api<{ diff: string }>(
      `/projects/${props.projectId}/git/diff?file=${encodeURIComponent(path)}&staged=${staged}`,
    )
    fileDiffText.value = res.diff
  } catch (err) {
    emit('error', err)
  }
}

async function loadCommitDetail(sha: string) {
  busy.value = true
  selectedFile.value = null
  try {
    selectedCommit.value = await api<CommitDetail>(`/projects/${props.projectId}/commits/${sha}`)
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
  }
}

watch(
  () => [props.projectId, props.gitStatus] as const,
  ([, st]) => {
    if (paneMode.value === 'changes' && st) {
      const first = st.staged[0] ? { path: st.staged[0].path, staged: true }
        : unstagedAll.value[0] ? { path: unstagedAll.value[0].path, staged: false }
        : null
      if (first && (!selectedFile.value || selectedFile.value.path !== first.path)) {
        loadWorktreeDiff(first.path, first.staged)
      } else if (!first) {
        selectedFile.value = null
        fileDiffText.value = ''
      }
    }
  },
  { immediate: true },
)

async function stage(files: string[], all = false) {
  busy.value = true
  try {
    await api(`/projects/${props.projectId}/git/stage`, 'POST', { files, all })
    emit('statusChanged')
  } catch (err) { emit('error', err) }
  finally { busy.value = false }
}

async function unstage(files: string[], all = false) {
  busy.value = true
  try {
    await api(`/projects/${props.projectId}/git/unstage`, 'POST', { files, all })
    emit('statusChanged')
  } catch (err) { emit('error', err) }
  finally { busy.value = false }
}

async function submitCommit() {
  if (!commitMessage.value.trim()) return
  busy.value = true
  try {
    const detail = await api<CommitDetail>(`/projects/${props.projectId}/git/commit`, 'POST', {
      message: commitMessage.value,
    })
    commitMessage.value = ''
    paneMode.value = 'commits'
    selectedCommit.value = detail
    emit('committed')
  } catch (err) { emit('error', err) }
  finally { busy.value = false }
}

function switchPane(mode: 'changes' | 'commits') {
  paneMode.value = mode
  if (mode === 'commits' && !selectedCommit.value && props.commits[0]) {
    loadCommitDetail(props.commits[0].sha)
  }
}

function parseDiffLines(raw: string) {
  if (!raw.trim()) return []
  return raw.split('\n').map(line => {
    const kind = line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff --git') || line.startsWith('index ')
      ? 'meta'
      : line.startsWith('@@') ? 'hunk'
      : line.startsWith('+') ? 'add'
      : line.startsWith('-') ? 'del'
      : 'ctx'
    return { kind, text: line }
  })
}

const statusShort: Record<string, string> = {
  added: 'A', modified: 'M', deleted: 'D', renamed: 'R', untracked: 'U',
}
</script>

<template>
  <div class="git-split">
    <aside class="card git-left">
      <div class="seg-tabs">
        <button type="button" :class="{ active: paneMode === 'changes' }" @click="switchPane('changes')">
          工作区变更 <span class="seg-count">{{ changeCount }}</span>
        </button>
        <button type="button" :class="{ active: paneMode === 'commits' }" @click="switchPane('commits')">
          提交记录 <span class="seg-count">{{ totalCommits }}</span>
        </button>
      </div>

      <template v-if="paneMode === 'changes'">
        <form v-if="isDeveloper" class="git-commit-box" @submit.prevent="submitCommit">
          <textarea
            v-model="commitMessage"
            name="commitMessage"
            rows="2"
            placeholder="输入提交说明 (Commit Message)…"
          ></textarea>
          <div class="row-between">
            <button
              type="button"
              class="btn btn-sm"
              :disabled="!changeCount"
              @click="emit('reviewRefs', 'HEAD', 'WORKTREE', '审阅工作区改动')"
            >
              影响审阅 →
            </button>
            <button
              type="submit"
              class="btn btn-primary btn-sm"
              :disabled="busy || !commitMessage.trim() || !(gitStatus?.staged.length)"
            >
              提交暂存 ({{ gitStatus?.staged.length || 0 }})
            </button>
          </div>
        </form>

        <div class="git-lists">
          <div class="git-group">
            <div class="git-group-head">
              <span>暂存区 ({{ gitStatus?.staged.length || 0 }})</span>
              <button
                v-if="isDeveloper && gitStatus?.staged.length"
                type="button"
                class="link-xs"
                @click="unstage([], true)"
              >
                全部取消
              </button>
            </div>
            <div v-for="item in gitStatus?.staged || []" :key="'s-' + item.path" class="git-file-row" :class="{ active: selectedFile?.path === item.path && selectedFile?.staged }">
              <button type="button" class="git-file-btn" @click="loadWorktreeDiff(item.path, true)">
                <span class="st-badge" :class="item.status">{{ statusShort[item.status] || 'M' }}</span>
                <span class="git-fname" :title="item.path">{{ item.path }}</span>
              </button>
              <button v-if="isDeveloper" type="button" class="icon-action" title="取消暂存" @click="unstage([item.path])">−</button>
            </div>
          </div>

          <div class="git-group">
            <div class="git-group-head">
              <span>未暂存 ({{ unstagedAll.length }})</span>
              <button
                v-if="isDeveloper && unstagedAll.length"
                type="button"
                class="link-xs"
                @click="stage([], true)"
              >
                全部暂存
              </button>
            </div>
            <div v-for="item in unstagedAll" :key="'u-' + item.path" class="git-file-row" :class="{ active: selectedFile?.path === item.path && !selectedFile?.staged }">
              <button type="button" class="git-file-btn" @click="loadWorktreeDiff(item.path, false)">
                <span class="st-badge" :class="item.status">{{ statusShort[item.status] || 'M' }}</span>
                <span class="git-fname" :title="item.path">{{ item.path }}</span>
              </button>
              <button v-if="isDeveloper" type="button" class="icon-action" title="暂存文件" @click="stage([item.path])">＋</button>
            </div>

            <div v-if="!changeCount" class="empty-box">工作区干净，无未提交改动</div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="git-lists">
          <button
            v-for="c in commits"
            :key="c.sha"
            type="button"
            class="commit-item"
            :class="{ active: selectedCommit?.sha === c.sha }"
            @click="loadCommitDetail(c.sha)"
          >
            <strong class="commit-item-title">{{ c.subject }}</strong>
            <div class="commit-item-meta">
              <code>{{ c.short_sha }}</code>
              <span>{{ c.author || '' }}</span>
              <span>{{ c.date }}</span>
            </div>
          </button>
        </div>
        <div class="git-pager">
          <button type="button" class="btn btn-sm" :disabled="offset === 0" @click="emit('paginate', -20)">上一页</button>
          <span>{{ offset + 1 }}–{{ offset + commits.length }} / {{ totalCommits }}</span>
          <button type="button" class="btn btn-sm" :disabled="offset + commits.length >= totalCommits" @click="emit('paginate', 20)">下一页</button>
        </div>
      </template>
    </aside>

    <section class="card git-right">
      <template v-if="paneMode === 'changes' && selectedFile">
        <div class="code-box-head">
          <div class="row-gap">
            <span class="badge" :class="selectedFile.staged ? 'badge-green' : 'badge-amber'">
              {{ selectedFile.staged ? '暂存区 Diff' : '工作区 Diff' }}
            </span>
            <code class="mono-path">{{ selectedFile.path }}</code>
          </div>
          <button type="button" class="btn btn-sm" @click="emit('openSource', selectedFile.path, 'WORKTREE')">
            打开文件
          </button>
        </div>
        <div v-if="!fileDiffText" class="empty-box">无行级文本差异</div>
        <div v-else class="diff-scroll">
          <div v-for="(ln, idx) in parseDiffLines(fileDiffText)" :key="idx" class="diff-line" :class="ln.kind">{{ ln.text }}</div>
        </div>
      </template>

      <template v-else-if="paneMode === 'commits' && selectedCommit">
        <div class="commit-detail-head">
          <div class="row-between">
            <h3>{{ selectedCommit.subject }}</h3>
            <button
              v-if="selectedCommit.parents.length && isDeveloper"
              type="button"
              class="btn btn-sm"
              @click="emit('reviewRefs', selectedCommit.parents[0], selectedCommit.sha, `审阅提交：${selectedCommit.subject}`)"
            >
              影响审阅 →
            </button>
          </div>
          <p v-if="selectedCommit.body" class="commit-body">{{ selectedCommit.body }}</p>
          <div class="commit-meta-bar">
            <span><strong>{{ selectedCommit.author }}</strong> 提交于 {{ selectedCommit.date }}</span>
            <code class="sha-chip">{{ selectedCommit.short_sha }}</code>
            <span>
              {{ selectedCommit.stats.files }} 个文件 ·
              <em class="plus">+{{ selectedCommit.stats.additions }}</em>
              <em class="minus"> -{{ selectedCommit.stats.deletions }}</em>
            </span>
          </div>
        </div>

        <div class="commit-files-scroll">
          <details v-for="f in selectedCommit.files" :key="f.path" class="commit-file-block" open>
            <summary>
              <div class="row-gap">
                <span class="st-badge" :class="f.status">{{ statusShort[f.status] || 'M' }}</span>
                <code>{{ f.path }}</code>
              </div>
              <div class="row-gap">
                <em class="plus">+{{ f.additions }}</em>
                <em class="minus">-{{ f.deletions }}</em>
                <button type="button" class="btn btn-sm" @click.stop="emit('openSource', f.path, selectedCommit.sha)">源码</button>
              </div>
            </summary>
            <div v-if="f.diff" class="diff-scroll compact">
              <div v-for="(ln, idx) in parseDiffLines(f.diff)" :key="idx" class="diff-line" :class="ln.kind">{{ ln.text }}</div>
            </div>
          </details>
        </div>
      </template>

      <div v-else class="empty-box large">
        {{ paneMode === 'changes' ? '选择左侧变更文件查看 Diff' : '选择左侧提交记录查看详情与差异' }}
      </div>
    </section>
  </div>
</template>
