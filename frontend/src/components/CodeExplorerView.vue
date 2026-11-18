<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type Commit, type RepoRefs, type Source, type Tree } from '../api'

const props = defineProps<{
  projectId: number
  repoName: string
  refs: RepoRefs | null
  latestCommit: Commit | null
  totalCommits: number
  initialRef?: string
  initialFile?: string
  highlightRange?: [number, number] | null
}>()

const emit = defineEmits<{
  openCommits: []
  error: [err: unknown]
}>()

const activeRef = ref(props.initialRef || props.refs?.current_branch || 'HEAD')
const currentDir = ref('')
const filterText = ref('')
const treeData = ref<Tree | null>(null)
const activeSource = ref<Source | null>(null)
const readmeContent = ref('')
const busy = ref(false)
const copied = ref(false)
const activeHighlight = ref<[number, number] | null>(props.highlightRange || null)

async function loadTree(refName: string, openFilePath?: string, range?: [number, number] | null) {
  busy.value = true
  try {
    activeRef.value = refName
    const t = await api<Tree>(`/projects/${props.projectId}/files?revision=${encodeURIComponent(refName)}&limit=3500`)
    treeData.value = t
    if (openFilePath) {
      const idx = openFilePath.lastIndexOf('/')
      currentDir.value = idx > 0 ? openFilePath.slice(0, idx) : ''
      await openFile(openFilePath, range || null)
    } else {
      activeSource.value = null
      activeHighlight.value = null
      await loadReadme(t)
    }
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
  }
}

async function loadReadme(t: Tree) {
  const prefix = currentDir.value ? `${currentDir.value}/` : ''
  const readme = t.files.find(f => f.path.toLowerCase() === `${prefix}readme.md`.toLowerCase())
  if (!readme) { readmeContent.value = ''; return }
  try {
    const res = await api<Source>(
      `/projects/${props.projectId}/source?revision=${encodeURIComponent(activeRef.value)}&file=${encodeURIComponent(readme.path)}`,
    )
    readmeContent.value = res.content
  } catch {
    readmeContent.value = ''
  }
}

async function openFile(path: string, range: [number, number] | null = null) {
  busy.value = true
  activeHighlight.value = range
  try {
    activeSource.value = await api<Source>(
      `/projects/${props.projectId}/source?revision=${encodeURIComponent(activeRef.value)}&file=${encodeURIComponent(path)}`,
    )
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
  }
}

function enterDir(dir: string) {
  currentDir.value = dir
  activeSource.value = null
  activeHighlight.value = null
  filterText.value = ''
  if (treeData.value) loadReadme(treeData.value)
}

watch(
  () => [props.projectId, props.initialRef, props.initialFile, props.highlightRange] as const,
  ([, refVal, fileVal, rangeVal]) => {
    const targetRef = refVal || props.refs?.current_branch || 'HEAD'
    loadTree(targetRef, fileVal || undefined, rangeVal || null)
  },
  { immediate: true },
)

interface DirEntry {
  kind: 'dir' | 'file'
  name: string
  path: string
}

// GitHub-style compact single-child folder collapsing (e.g. src/main/kotlin/com/...)
const entries = computed<DirEntry[]>(() => {
  const all = treeData.value?.files || []
  const q = filterText.value.trim().toLowerCase()
  if (q) {
    return all
      .filter(f => f.path.toLowerCase().includes(q))
      .slice(0, 80)
      .map(f => ({ kind: 'file' as const, name: f.path, path: f.path }))
  }

  const prefix = currentDir.value ? `${currentDir.value}/` : ''
  const childrenMap = new Map<string, string[]>()
  const directFiles: DirEntry[] = []

  for (const f of all) {
    if (!f.path.startsWith(prefix)) continue
    const rest = f.path.slice(prefix.length)
    const slash = rest.indexOf('/')
    if (slash === -1) {
      directFiles.push({ kind: 'file', name: rest, path: f.path })
    } else {
      const seg = rest.slice(0, slash)
      const list = childrenMap.get(seg)
      if (list) list.push(rest.slice(slash + 1))
      else childrenMap.set(seg, [rest.slice(slash + 1)])
    }
  }

  const dirs: DirEntry[] = []
  for (const [seg, subPaths] of childrenMap.entries()) {
    let display = seg
    let fullDir = prefix + seg
    let currentSubs = subPaths
    // Collapse chains where every path shares a single subfolder and zero direct files
    while (currentSubs.length > 0 && currentSubs.every(s => s.includes('/'))) {
      const nextSegs = new Set(currentSubs.map(s => s.slice(0, s.indexOf('/'))))
      if (nextSegs.size !== 1) break
      const only = [...nextSegs][0]
      display += `/${only}`
      fullDir += `/${only}`
      currentSubs = currentSubs.map(s => s.slice(only.length + 1))
    }
    dirs.push({ kind: 'dir', name: display, path: fullDir })
  }

  dirs.sort((a, b) => a.name.localeCompare(b.name))
  directFiles.sort((a, b) => a.name.localeCompare(b.name))
  return [...dirs, ...directFiles]
})

const breadcrumbs = computed(() => {
  const target = activeSource.value ? activeSource.value.path : currentDir.value
  if (!target) return []
  const parts = target.split('/')
  return parts.map((part, idx) => ({
    label: part,
    path: parts.slice(0, idx + 1).join('/'),
    isLast: idx === parts.length - 1,
  }))
})

const sourceLines = computed(() => (activeSource.value?.content || '').split('\n'))

async function copyCode() {
  if (!activeSource.value || !navigator.clipboard) return
  await navigator.clipboard.writeText(activeSource.value.content)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
</script>

<template>
  <div class="stack-md">
    <div class="code-toolbar">
      <div class="toolbar-left">
        <div class="ref-select-wrap">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.493 2.493 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Z"/></svg>
          <select :value="activeRef" name="codeRefSelect" aria-label="切换分支或版本" @change="loadTree(($event.target as HTMLSelectElement).value)">
            <option value="WORKTREE">工作区 (未提交实时)</option>
            <optgroup v-if="refs?.branches?.length" label="分支 (Branches)">
              <option v-for="b in refs.branches" :key="b.name" :value="b.name">
                {{ b.name }}{{ b.current ? ' • 当前' : '' }}
              </option>
            </optgroup>
            <optgroup v-if="refs?.tags?.length" label="标签 (Tags)">
              <option v-for="t in refs.tags" :key="t.name" :value="t.name">{{ t.name }}</option>
            </optgroup>
            <option v-if="activeRef !== 'WORKTREE' && !refs?.branches?.some(b => b.name === activeRef) && !refs?.tags?.some(t => t.name === activeRef)" :value="activeRef">
              {{ activeRef.slice(0, 10) }}
            </option>
          </select>
        </div>

        <nav class="repo-crumbs" aria-label="路径导航">
          <button type="button" class="crumb-root" @click="enterDir('')">{{ repoName }}</button>
          <template v-for="bc in breadcrumbs" :key="bc.path">
            <span class="crumb-sep">/</span>
            <span v-if="bc.isLast && activeSource" class="crumb-current">{{ bc.label }}</span>
            <button v-else type="button" class="crumb-btn" @click="enterDir(bc.path)">{{ bc.label }}</button>
          </template>
        </nav>
      </div>

      <div class="toolbar-right">
        <input
          v-model="filterText"
          name="fileSearch"
          class="compact-input"
          placeholder="查找文件…"
          @input="activeSource = null"
        />
        <button type="button" class="btn" @click="emit('openCommits')">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"/></svg>
          <strong>{{ totalCommits }}</strong> 次提交
        </button>
      </div>
    </div>

    <div v-if="activeSource" class="card code-box">
      <div class="code-box-head">
        <div class="row-gap">
          <button type="button" class="btn btn-sm" @click="enterDir(currentDir)">← 返回目录</button>
          <code class="mono-path">{{ activeSource.path }}</code>
          <span class="muted">{{ sourceLines.length }} 行</span>
          <span v-if="activeHighlight" class="badge badge-amber">L{{ activeHighlight[0] }}–{{ activeHighlight[1] }}</span>
        </div>
        <button type="button" class="btn btn-sm" @click="copyCode">{{ copied ? '已复制' : '复制' }}</button>
      </div>
      <div class="code-scroll">
        <pre class="code-table"><code><div
          v-for="(ln, idx) in sourceLines"
          :key="idx"
          class="code-line-row"
          :class="{ highlighted: activeHighlight && idx + 1 >= activeHighlight[0] && idx + 1 <= activeHighlight[1] }"
        ><span class="gutter-ln">{{ idx + 1 }}</span><span class="code-cell">{{ ln }}</span></div></code></pre>
      </div>
    </div>

    <template v-else>
      <div class="card tree-box">
        <div v-if="latestCommit" class="commit-banner">
          <div class="row-gap">
            <span class="commit-author">{{ latestCommit.author || 'Git' }}</span>
            <span class="commit-msg">{{ latestCommit.subject }}</span>
          </div>
          <div class="row-gap">
            <code class="sha-chip">{{ latestCommit.short_sha }}</code>
            <span class="muted">{{ latestCommit.date }}</span>
          </div>
        </div>

        <div v-if="currentDir && !filterText" class="tree-row up-row" @click="enterDir(currentDir.includes('/') ? currentDir.slice(0, currentDir.lastIndexOf('/')) : '')">
          <span class="tree-icon">..</span>
          <span class="tree-name">返回上级</span>
        </div>

        <div v-if="busy && !entries.length" class="empty-box">读取目录中…</div>
        <div v-else-if="!entries.length" class="empty-box">未找到匹配文件</div>

        <button
          v-for="item in entries"
          :key="item.path"
          type="button"
          class="tree-row"
          @click="item.kind === 'dir' ? enterDir(item.path) : openFile(item.path)"
        >
          <svg v-if="item.kind === 'dir'" class="icon-dir" viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
            <path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0 0 16 13.25v-8.5A1.75 1.75 0 0 0 14.25 3H7.5a.25.25 0 0 1-.2-.1l-.9-1.2C6.07 1.26 5.55 1 5 1H1.75Z"/>
          </svg>
          <svg v-else class="icon-file" viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
            <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"/>
          </svg>
          <span class="tree-name" :class="{ bold: item.kind === 'dir' }">{{ item.name }}</span>
        </button>
      </div>

      <div v-if="readmeContent && !filterText" class="card readme-box">
        <div class="card-head">
          <span class="card-title">README.md</span>
        </div>
        <pre class="readme-pre">{{ readmeContent }}</pre>
      </div>
    </template>
  </div>
</template>
