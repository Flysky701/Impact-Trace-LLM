<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  api, ApiError,
  type AnalysisSummary, type Anchor, type DrawerFocus, type GitStatus,
  type History, type LlmSettings, type MaintenanceNote, type Project,
  type RepoOverview, type RepoRefs, type User,
} from './api'
import CodeExplorerView from './components/CodeExplorerView.vue'
import ContextDrawer from './components/ContextDrawer.vue'
import GitWorkspaceView from './components/GitWorkspaceView.vue'
import LlmSettingsModal from './components/LlmSettingsModal.vue'
import MaintenanceView from './components/MaintenanceView.vue'
import OverviewView from './components/OverviewView.vue'
import ReviewView from './components/ReviewView.vue'

type TabId = 'code' | 'overview' | 'git' | 'review' | 'maintenance'

const user = ref<User | null>(null)
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const restoring = ref(true)

const projects = ref<Project[]>([])
const reviewers = ref<User[]>([])
const roots = ref<string[]>([])
const llmSettings = ref<LlmSettings | null>(null)
const showLlmModal = ref(false)

const selected = ref<Project | null>(null)
const activeTab = ref<TabId>('code')

const refsData = ref<RepoRefs | null>(null)
const gitStatus = ref<GitStatus | null>(null)
const history = ref<History | null>(null)
const offset = ref(0)

const overview = ref<RepoOverview | null>(null)
const overviewLoading = ref(false)
const analyses = ref<AnalysisSummary[]>([])
const notes = ref<MaintenanceNote[]>([])
const drawerFocus = ref<DrawerFocus | null>(null)

const targetCodeRef = ref('')
const targetCodeFile = ref('')
const highlightRange = ref<[number, number] | null>(null)
const presetCompare = ref<{ base: string; head: string; title: string } | null>(null)

const showForm = ref(false)
const editingProject = ref(false)
const name = ref('')
const repositoryPath = ref('')
const description = ref('')
const reviewerId = ref<number | null>(null)

let generation = 0
const isDeveloper = computed(() => user.value?.role === 'developer')
const isReviewer = computed(() => user.value?.role === 'reviewer')
const openNoteCount = computed(() => notes.value.filter(n => !n.resolved).length)
const dirtyCount = computed(() =>
  (gitStatus.value?.staged.length || 0) +
  (gitStatus.value?.unstaged.length || 0) +
  (gitStatus.value?.untracked.length || 0)
)

function clearSession() {
  generation++
  loading.value = false; overviewLoading.value = false
  user.value = null; projects.value = []; selected.value = null
  refsData.value = null; gitStatus.value = null; history.value = null
  overview.value = null; analyses.value = []; notes.value = []; drawerFocus.value = null
  roots.value = []; reviewers.value = []; showForm.value = false; editingProject.value = false
  llmSettings.value = null; showLlmModal.value = false
  password.value = ''; name.value = ''; repositoryPath.value = ''; description.value = ''
  reviewerId.value = null
}

function failure(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) clearSession()
  error.value = cause instanceof Error ? cause.message : '操作失败，请重试。'
}

async function loadWorkspaceMeta() {
  projects.value = await api<Project[]>('/projects')
  llmSettings.value = await api<LlmSettings>('/settings/llm').catch(() => null)
  if (isDeveloper.value) {
    reviewers.value = await api<User[]>('/reviewers')
    roots.value = (await api<{ repository_roots: string[] }>('/config')).repository_roots
  }
}

async function login() {
  loading.value = true; error.value = ''
  try {
    user.value = await api<User>('/auth/login', 'POST', { username: username.value, password: password.value })
    password.value = ''
    await loadWorkspaceMeta()
    if (projects.value.length) await selectProject(projects.value[0])
  } catch (cause) { failure(cause) }
  finally { loading.value = false }
}

async function logout() {
  loading.value = true; error.value = ''
  try { await api('/auth/logout', 'POST'); clearSession() }
  catch (cause) { failure(cause) }
  finally { loading.value = false }
}

async function createProject() {
  loading.value = true; error.value = ''
  try {
    const project = await api<Project>('/projects', 'POST', {
      name: name.value, repository_path: repositoryPath.value,
      description: description.value, reviewer_id: reviewerId.value,
    })
    await loadWorkspaceMeta()
    showForm.value = false; name.value = ''; repositoryPath.value = ''; description.value = ''
    await selectProject(project)
  } catch (cause) { failure(cause) }
  finally { loading.value = false }
}

function toggleEditProject() {
  if (!selected.value) return
  editingProject.value = !editingProject.value
  name.value = selected.value.name
  description.value = selected.value.description
  reviewerId.value = selected.value.reviewer_id
}

async function saveProjectEdit() {
  if (!selected.value) return
  loading.value = true; error.value = ''
  try {
    const updated = await api<Project>(`/projects/${selected.value.id}`, 'PATCH', {
      name: name.value, description: description.value, reviewer_id: reviewerId.value,
    })
    selected.value = updated
    editingProject.value = false
    projects.value = await api<Project[]>('/projects')
  } catch (cause) { failure(cause) }
  finally { loading.value = false }
}

async function refreshGitStatus() {
  if (!selected.value) return
  gitStatus.value = await api<GitStatus>(`/projects/${selected.value.id}/git/status`).catch(() => null)
}

async function refreshRefs() {
  if (!selected.value) return
  refsData.value = await api<RepoRefs>(`/projects/${selected.value.id}/refs`).catch(() => null)
}

async function refreshNotes() {
  if (!selected.value) return
  notes.value = await api<MaintenanceNote[]>(`/projects/${selected.value.id}/notes`).catch(() => [])
}

async function refreshAnalyses() {
  if (!selected.value) return
  analyses.value = await api<AnalysisSummary[]>(`/projects/${selected.value.id}/analyses`).catch(() => [])
}

async function loadHistory() {
  if (!selected.value) return
  const current = ++generation
  try {
    const res = await api<History>(`/projects/${selected.value.id}/commits?offset=${offset.value}`)
    if (current === generation) history.value = res
  } catch (cause) { if (current === generation) failure(cause) }
}

async function paginateHistory(delta: number) {
  offset.value = Math.max(0, offset.value + delta)
  await loadHistory()
}

async function loadOverview(forceAi = false) {
  if (!selected.value) return
  const pid = selected.value.id
  overviewLoading.value = true; error.value = ''
  try {
    overview.value = forceAi
      ? await api<RepoOverview>(`/projects/${pid}/overview/generate`, 'POST', { revision: 'HEAD', use_llm: true })
      : await api<RepoOverview>(`/projects/${pid}/overview?revision=HEAD`)
  } catch (cause) { failure(cause) }
  finally { overviewLoading.value = false }
}

async function selectProject(project: Project) {
  selected.value = project
  drawerFocus.value = null
  editingProject.value = false
  offset.value = 0
  targetCodeRef.value = ''
  targetCodeFile.value = ''
  highlightRange.value = null
  overview.value = null
  await Promise.all([
    refreshRefs(),
    refreshGitStatus(),
    loadHistory(),
    loadOverview(false),
    refreshAnalyses(),
    refreshNotes(),
  ])
}

async function onCommitted() {
  offset.value = 0
  await Promise.all([refreshRefs(), refreshGitStatus(), loadHistory(), loadOverview(false)])
}

function jumpToAnchor(anchor: Anchor, rev: string) {
  drawerFocus.value = null
  targetCodeRef.value = rev || 'HEAD'
  targetCodeFile.value = anchor.path
  highlightRange.value = [anchor.line, anchor.end || anchor.line]
  activeTab.value = 'code'
}

function openSourceFromGit(path: string, rev: string) {
  targetCodeRef.value = rev
  targetCodeFile.value = path
  highlightRange.value = null
  activeTab.value = 'code'
}

function triggerReview(base: string, head: string, title: string) {
  presetCompare.value = { base, head, title }
  activeTab.value = 'review'
}

onMounted(async () => {
  try {
    user.value = await api<User>('/auth/me')
    await loadWorkspaceMeta()
    if (projects.value.length) await selectProject(projects.value[0])
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) clearSession()
    else failure(cause)
  } finally {
    restoring.value = false
  }
})
</script>

<template>
  <div class="shell">
    <header class="global-nav">
      <div class="nav-left">
        <a class="logo" href="/" aria-label="ImpactTrace">
          <span class="logo-mark">IT</span>
          <span class="logo-text">ImpactTrace</span>
        </a>

        <template v-if="user">
          <span class="nav-divider">/</span>
          <div class="repo-pills">
            <button
              v-for="proj in projects"
              :key="proj.id"
              type="button"
              class="repo-pill"
              :class="{ active: selected?.id === proj.id }"
              @click="selectProject(proj)"
            >
              {{ proj.name }}
            </button>
            <button v-if="isDeveloper" type="button" class="repo-add" @click="showForm = !showForm">
              {{ showForm ? '取消' : '+ 接入仓库' }}
            </button>
          </div>
        </template>
      </div>

      <div v-if="user" class="nav-right">
        <button
          type="button"
          class="ai-status-btn"
          :class="{ on: llmSettings?.configured }"
          @click="showLlmModal = true"
        >
          <span class="status-dot"></span>
          <span>{{ llmSettings?.configured ? llmSettings.model : 'AI 接口' }}</span>
        </button>
        <span class="user-chip">
          {{ user.username }} · {{ isDeveloper ? '开发' : '审阅' }}
        </span>
        <button type="button" class="nav-logout" :disabled="loading" @click="logout">退出</button>
      </div>
    </header>

    <div v-if="error" class="container" style="padding-top: 12px; padding-bottom: 0">
      <div class="alert-bar err" role="alert">
        <span>{{ error }}</span>
        <button type="button" class="icon-close" aria-label="关闭提示" @click="error = ''">✕</button>
      </div>
    </div>

    <div v-if="restoring" class="empty-box large">加载中…</div>

    <main v-else-if="!user" class="auth-wrap">
      <form class="card auth-card" @submit.prevent="login">
        <div class="auth-head">
          <span class="logo-mark large">IT</span>
          <h1>登录本地代码工作台</h1>
        </div>
        <label>
          用户名
          <input v-model="username" name="username" autocomplete="username" required maxlength="80" />
        </label>
        <label>
          密码
          <input v-model="password" name="password" type="password" autocomplete="current-password" required maxlength="256" />
        </label>
        <button class="btn btn-primary btn-block" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>
    </main>

    <template v-else>
      <div v-if="showForm && isDeveloper" class="container" style="padding-top: 14px; padding-bottom: 0">
        <form class="card form-panel" @submit.prevent="createProject">
          <div class="row-between" style="margin-bottom: 10px">
            <strong>接入本地 Git 仓库</strong>
            <small class="muted">允许目录：{{ roots.join(' ; ') }}</small>
          </div>
          <div class="grid-4">
            <label>
              仓库名称
              <input v-model="name" name="projectName" required maxlength="100" placeholder="LimingjieDesktop" />
            </label>
            <label class="span-2">
              本地路径
              <input v-model="repositoryPath" name="repositoryPath" required placeholder="D:\Project\LimingjieDesktop" />
            </label>
            <label>
              指定审核人
              <select v-model="reviewerId" name="reviewer">
                <option :value="null">不指定</option>
                <option v-for="person in reviewers" :key="person.id" :value="person.id">{{ person.username }}</option>
              </select>
            </label>
          </div>
          <div class="row-between" style="margin-top: 10px">
            <input v-model="description" name="description" placeholder="备注（可选）" style="max-width: 420px" />
            <button class="btn btn-primary btn-sm" :disabled="loading">{{ loading ? '读取中…' : '确认接入' }}</button>
          </div>
        </form>
      </div>

      <div v-if="!selected" class="container">
        <div class="card empty-box large">
          <p>{{ isDeveloper ? '尚未接入仓库' : '暂无分配给你的仓库' }}</p>
          <button v-if="isDeveloper" type="button" class="btn btn-primary" style="margin-top: 10px" @click="showForm = true">
            + 接入本地仓库
          </button>
        </div>
      </div>

      <template v-else>
        <div class="repo-header">
          <div class="container repo-header-inner">
            <div class="repo-title-row">
              <div class="row-gap">
                <h1 class="repo-name">{{ selected.name }}</h1>
                <code class="repo-path-badge">{{ selected.repository_path }}</code>
                <span v-if="refsData?.current_branch" class="branch-badge">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor"><path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.493 2.493 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Z"/></svg>
                  {{ refsData.current_branch }}
                </span>
                <button
                  v-if="dirtyCount > 0"
                  type="button"
                  class="dirty-badge"
                  @click="activeTab = 'git'"
                >
                  {{ dirtyCount }} 处未提交变更
                </button>
              </div>

              <button v-if="isDeveloper" type="button" class="btn btn-sm" @click="toggleEditProject">
                {{ editingProject ? '收起设置' : '设置' }}
              </button>
            </div>

            <form v-if="editingProject && isDeveloper" class="edit-inline" @submit.prevent="saveProjectEdit">
              <input v-model="name" name="editProjectName" required maxlength="100" placeholder="名称" />
              <input v-model="description" name="editDescription" placeholder="备注" />
              <select v-model="reviewerId" name="editReviewer">
                <option :value="null">无审核人</option>
                <option v-for="person in reviewers" :key="person.id" :value="person.id">{{ person.username }}</option>
              </select>
              <button type="submit" class="btn btn-primary btn-sm" :disabled="loading">保存</button>
            </form>

            <nav class="repo-tabs" aria-label="仓库视图">
              <button type="button" :class="{ active: activeTab === 'code' }" @click="activeTab = 'code'; targetCodeFile = ''">
                <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="m11.28 3.22 4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L13.94 8l-3.72-3.72a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215Zm-6.56 0a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L2.06 8l3.72 3.72a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L.47 8.53a.75.75 0 0 1 0-1.06Z"/></svg>
                代码
              </button>
              <button type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
                <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M1.75 1h12.5c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0 1 14.25 15H1.75A1.75 1.75 0 0 1 0 13.25V2.75C0 1.784.784 1 1.75 1ZM1.5 2.75v10.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V2.75a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25ZM5 6.25a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5A.75.75 0 0 1 5 6.25Zm0 3.5a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Z"/></svg>
                架构导览
              </button>
              <button type="button" :class="{ active: activeTab === 'git' }" @click="activeTab = 'git'">
                <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"/></svg>
                Git 工作区
                <em v-if="dirtyCount" class="tab-count">{{ dirtyCount }}</em>
              </button>
              <button type="button" :class="{ active: activeTab === 'review' }" @click="activeTab = 'review'">
                <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M5.22 14.78a.75.75 0 0 0 1.06-1.06L4.56 12h8.69a.75.75 0 0 0 0-1.5H4.56l1.72-1.72a.75.75 0 0 0-1.06-1.06l-3 3a.75.75 0 0 0 0 1.06l3 3Zm5.56-6.5a.75.75 0 1 0 1.06-1.06l-3-3a.75.75 0 0 0-1.06 0l-3 3a.75.75 0 0 0 1.06 1.06L7.56 6.5h8.69a.75.75 0 0 0 0-1.5H7.56l1.72-1.72Z"/></svg>
                影响审阅
                <em v-if="analyses.length" class="tab-count">{{ analyses.length }}</em>
              </button>
              <button type="button" :class="{ active: activeTab === 'maintenance' }" @click="activeTab = 'maintenance'">
                <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v9.5A1.75 1.75 0 0 1 14.25 13H8.06l-2.573 2.573A1.458 1.458 0 0 1 3 14.543V13H1.75A1.75 1.75 0 0 1 0 11.25Zm1.75-.25a.25.25 0 0 0-.25.25v9.5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h6.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25Z"/></svg>
                问答与便签
                <em v-if="openNoteCount" class="tab-count">{{ openNoteCount }}</em>
              </button>
            </nav>
          </div>
        </div>

        <main class="container workspace-main">
          <CodeExplorerView
            v-if="activeTab === 'code'"
            :project-id="selected.id"
            :repo-name="selected.name"
            :refs="refsData"
            :latest-commit="history?.commits?.[0] || null"
            :total-commits="history?.total || 0"
            :initial-ref="targetCodeRef"
            :initial-file="targetCodeFile"
            :highlight-range="highlightRange"
            @open-commits="activeTab = 'git'"
            @error="failure"
          />

          <OverviewView
            v-else-if="activeTab === 'overview'"
            :overview="overview"
            :loading="overviewLoading"
            :llm-configured="Boolean(llmSettings?.configured)"
            :notes="notes"
            @inspect="f => drawerFocus = f"
            @generate-ai="loadOverview(true)"
            @open-settings="showLlmModal = true"
          />

          <GitWorkspaceView
            v-else-if="activeTab === 'git'"
            :project-id="selected.id"
            :is-developer="isDeveloper"
            :git-status="gitStatus"
            :commits="history?.commits || []"
            :total-commits="history?.total || 0"
            :offset="offset"
            @status-changed="refreshGitStatus"
            @committed="onCommitted"
            @paginate="paginateHistory"
            @open-source="openSourceFromGit"
            @review-refs="triggerReview"
            @error="failure"
          />

          <ReviewView
            v-else-if="activeTab === 'review'"
            :project-id="selected.id"
            :is-developer="isDeveloper"
            :is-reviewer="isReviewer"
            :llm-configured="Boolean(llmSettings?.configured)"
            :commits="history?.commits || []"
            :analyses="analyses"
            :preset-compare="presetCompare"
            @preset-consumed="presetCompare = null"
            @inspect="f => drawerFocus = f"
            @open-anchor="jumpToAnchor"
            @analyses-changed="refreshAnalyses"
            @open-settings="showLlmModal = true"
          />

          <MaintenanceView
            v-else
            :project-id="selected.id"
            :revision="overview?.commit || 'HEAD'"
            :roles="overview?.roles || []"
            :hotspots="overview?.hotspots || []"
            :notes="notes"
            @inspect="f => drawerFocus = f"
            @open-anchor="jumpToAnchor"
            @notes-changed="refreshNotes"
          />
        </main>
      </template>
    </template>

    <ContextDrawer
      v-if="drawerFocus && selected"
      :project-id="selected.id"
      :focus="drawerFocus"
      :notes="notes"
      @close="drawerFocus = null"
      @open-anchor="jumpToAnchor"
      @note-created="refreshNotes"
    />

    <LlmSettingsModal
      v-if="showLlmModal"
      :settings="llmSettings"
      :is-developer="isDeveloper"
      @close="showLlmModal = false"
      @updated="val => llmSettings = val"
    />
  </div>
</template>
