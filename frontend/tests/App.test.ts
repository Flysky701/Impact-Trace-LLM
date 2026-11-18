import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../src/App.vue'
import {
  api, ApiError,
  type AnalysisDetail, type AnalysisSummary, type CommitDetail,
  type GitStatus, type LlmSettings, type MaintenanceNote, type RepoOverview,
} from '../src/api'

vi.mock('../src/api', async importOriginal => {
  const original = await importOriginal<typeof import('../src/api')>()
  return { ...original, api: vi.fn() }
})

const mockApi = vi.mocked(api)
const developer = { id: 1, username: 'dev', role: 'developer' as const }
const reviewer = { id: 2, username: 'review', role: 'reviewer' as const }
const baseProject = {
  id: 1, name: 'LimingjieDesktop', description: '桌面总控',
  repository_path: 'D:/Project/LimingjieDesktop', owner_id: 1, reviewer_id: 2, created_at: 1,
}
const sha = 'a'.repeat(40)
const sha2 = 'b'.repeat(40)
const commit1 = { sha, short_sha: 'aaaaaaa', author: 'dev', date: '2026-11-06', subject: 'Adjust account sync order' }
const commit2 = { sha: sha2, short_sha: 'bbbbbbb', author: 'dev', date: '2026-11-01', subject: 'Init coordinator' }

const sampleOverview: RepoOverview = {
  repoName: 'LimingjieDesktop',
  revision: sha,
  commit: sha,
  language: 'kotlin',
  sourceMode: 'heuristic',
  modelName: '',
  headline: '连接外部设备抓图并通过画面识别自动执行操作的桌面总控系统。',
  narrative: '由桌面总控、设备操控、视觉识别与核心业务账本协同运转。',
  roles: [
    {
      id: 'app', title: '桌面界面与总控中枢', subtitle: '统筹账号准备与任务启停',
      plainHow: '由桌面入口统一装配调度各子模块。', fileCount: 40, lineCount: 9800,
      anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 10, end: 25, label: '总控入口' }],
    },
    {
      id: 'device', title: '设备手脚：抓图与触控', subtitle: '连接设备抓图并发送点击',
      plainHow: '通过底层命令采集屏幕画面。', fileCount: 25, lineCount: 4200,
      anchors: [{ path: 'desktop/device/Adb.kt', line: 1, end: 15, label: '设备连接' }],
    },
  ],
  roleFlows: [
    { from: 'app', to: 'device', action: '下发抓图与点击指令', detail: '总控调度设备执行动作' },
  ],
  storylines: [
    {
      id: 'story-1', title: '启动前准备共享账号', when: '选定账号时', outcome: '档案与凭据就绪',
      steps: [
        {
          stepNo: 1, what: '同步账号档案到本地账本', why: '保证记录完整',
          howPlain: '在事务中写入本地数据库记录。', moduleId: 'app',
          anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 12, end: 20, label: '账号同步步骤' }],
        },
      ],
    },
    {
      id: 'story-2', title: '画面识别主循环', when: '任务启动后', outcome: '推进界面操作',
      steps: [
        {
          stepNo: 1, what: '抓取画面并判读当前页面', why: '识别状态',
          howPlain: '调用视觉模块识别坐标。', moduleId: 'device',
          anchors: [{ path: 'desktop/device/Adb.kt', line: 5, end: 12, label: '抓图步骤' }],
        },
      ],
    },
  ],
  dataCards: [
    {
      id: 'ent-1', plainName: '账号档案表', rawName: 'accounts',
      purpose: '保存登记账号基础信息', fieldCount: 8, relations: ['被自动运行记录引用'],
      anchors: [{ path: 'desktop/shared/Account.kt', line: 1, end: 18, label: 'accounts' }],
    },
  ],
  hotspots: [
    {
      id: 'hp-1', title: '进入后界面分派逻辑高度集中',
      whyHard: '超过 900 行且多分支。',
      splitIdea: '按不同页面拆分为独立处理器。',
      severity: 'high', metrics: '908 行 · 149 分支', moduleId: 'app',
      anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 15, end: 30, label: '复杂分支' }],
    },
  ],
  stats: { files: 290, lines: 64616, functions: 2540, classes: 1249, testFiles: 222, parseErrorFiles: 0 },
}

const sampleAnalysisDetail: AnalysisDetail = {
  id: 10,
  project_id: 1,
  created_by: 1,
  task_type: 'commit_compare',
  title: '审阅账号同步顺序调整',
  user_prompt: '将数据库投影移到凭据更新之前',
  raw_log: '',
  base_ref: sha2,
  head_ref: 'WORKTREE',
  base_sha: sha2,
  head_sha: 'WORKTREE',
  status: 'completed',
  llm_status: 'not_requested',
  headline: '调整了桌面总控中的账号准备执行顺序。',
  diagnostics: { changedFileCount: 1, changedFlowCount: 1, impactCount: 1, parseErrorFiles: 0 },
  review_count: 0,
  latest_verdict: null,
  created_at: 100,
  result: {
    baseSha: sha2,
    headSha: 'WORKTREE',
    headCommit: sha,
    language: 'kotlin',
    plainSummary: {
      mode: 'heuristic',
      model: '',
      headline: '调整了桌面总控中的账号准备执行顺序。',
      beforeVsAfter: '先同步档案再更新凭据。',
      riskPoints: [
        {
          title: '核对中途取消状态一致性',
          detail: '确认投影成功后若取消操作可重试。',
          anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 12, end: 22, label: '顺序调整处' }],
        },
      ],
      testSuggestions: ['SharedDataIntegrationTest'],
    },
    flowComparisons: [
      {
        id: 'fc-1', plainTitle: '准备共享账号流程', symbolName: 'prepareSharedAccount',
        moduleId: 'app', status: 'modified', path: 'desktop/app/src/main/kotlin/Main.kt',
        beforeSteps: [{
          stepNo: 1, what: '旧版先更新凭据', why: '原顺序', howPlain: '旧实现',
          moduleId: 'app', changeTag: 'modified',
          anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 10, end: 15, label: '旧步骤' }],
        }],
        afterSteps: [{
          stepNo: 1, what: '新版先同步本地档案', why: '新顺序', howPlain: '新实现',
          moduleId: 'app', changeTag: 'modified',
          anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 12, end: 18, label: '新步骤' }],
        }],
      },
    ],
    impactRadius: [
      {
        id: 'imp-1', plainName: '启动自动任务环节', symbolName: 'startAutoRun',
        moduleId: 'app', distance: 1, alsoChanged: false,
        chain: 'prepareSharedAccount → startAutoRun',
        reason: '直接调用了被改逻辑。',
        anchor: { path: 'desktop/app/src/main/kotlin/Main.kt', line: 40, end: 55, label: 'startAutoRun' },
      },
    ],
    fileChanges: [
      { path: 'desktop/app/src/main/kotlin/Main.kt', status: 'modified', additions: 5, deletions: 4, diff: '@@ -10,2 +10,2 @@\n-old\n+new' },
    ],
    diagnostics: { changedFileCount: 1, changedFlowCount: 1, impactCount: 1, parseErrorFiles: 0 },
  },
  reviews: [],
}

const sampleCommitDetail: CommitDetail = {
  sha, short_sha: 'aaaaaaa', author: 'dev', email: 'dev@test', date: '2026-11-06 12:00:00',
  parents: [sha2], subject: 'Adjust account sync order', body: 'Detailed body',
  files: [{ path: 'desktop/app/src/main/kotlin/Main.kt', status: 'modified', additions: 4, deletions: 2, diff: '@@ -1,2 +1,2 @@\n-old\n+new' }],
  stats: { files: 1, additions: 4, deletions: 2 },
}

let actor: typeof developer | typeof reviewer | null
let savedProjects: typeof baseProject[]
let savedNotes: MaintenanceNote[]
let savedAnalyses: AnalysisSummary[]
let currentDetail: AnalysisDetail
let gitSt: GitStatus
let llmCfg: LlmSettings
let wrapper: VueWrapper | undefined

async function handler(path: string, method = 'GET', body?: any): Promise<unknown> {
  if (path === '/auth/me') {
    if (!actor) throw new ApiError(401, '请登录')
    return actor
  }
  if (path === '/auth/login') { actor = developer; return developer }
  if (path === '/auth/logout') { actor = null; return undefined }
  if (path === '/reviewers') return [reviewer]
  if (path === '/config') return { repository_roots: ['D:/Project'] }
  if (path === '/settings/llm' && method === 'GET') return llmCfg
  if (path === '/settings/llm' && method === 'PUT') {
    llmCfg = {
      ...llmCfg, provider: body.provider, base_url: body.base_url, model: body.model,
      configured: body.clear_key ? false : Boolean(body.api_key || llmCfg.configured),
      masked_key: body.clear_key ? '' : 'sk-1••••9999',
    }
    return llmCfg
  }
  if (path === '/settings/llm/test') return { ok: true, model: body.model, latency_ms: 95, reply: 'OK' }
  if (path === '/projects' && method === 'POST') {
    const created = { ...baseProject, name: body.name, description: body.description, repository_path: body.repository_path, reviewer_id: body.reviewer_id }
    savedProjects = [created]
    return created
  }
  if (path === '/projects/1' && method === 'PATCH') {
    savedProjects[0] = { ...savedProjects[0], name: body.name, description: body.description, reviewer_id: body.reviewer_id }
    return savedProjects[0]
  }
  if (path === '/projects') return savedProjects
  if (path === '/projects/1/refs') {
    return {
      current_branch: 'main', head_sha: sha,
      branches: [{ name: 'main', sha, short_sha: 'aaaaaaa', date: '2026-11-06', subject: 'Adjust', current: true }],
      tags: [{ name: 'v1.0', short_sha: 'bbbbbbb', date: '2026-11-01' }],
    }
  }
  if (path === '/projects/1/git/status') return gitSt
  if (path.startsWith('/projects/1/git/diff')) return { path: 'Main.kt', staged: false, diff: '@@ -1,2 +1,2 @@\n-oldLine\n+newLine' }
  if (path === '/projects/1/git/stage') {
    gitSt = { ...gitSt, staged: [...gitSt.unstaged], unstaged: [], untracked: [] }
    return gitSt
  }
  if (path === '/projects/1/git/unstage') {
    gitSt = { ...gitSt, unstaged: [...gitSt.staged], staged: [] }
    return gitSt
  }
  if (path === '/projects/1/git/commit') {
    gitSt = { ...gitSt, clean: true, staged: [], unstaged: [], untracked: [] }
    return sampleCommitDetail
  }
  if (path.startsWith('/projects/1/commits/')) return sampleCommitDetail
  if (path.includes('/commits')) return { revision: sha, total: 25, commits: [commit1, commit2] }
  if (path.includes('/files')) {
    return {
      revision: sha, truncated: false,
      files: [
        { path: 'README.md', oid: sha },
        { path: 'desktop/app/src/main/kotlin/Main.kt', oid: sha },
        { path: 'desktop/device/Adb.kt', oid: sha },
      ],
    }
  }
  if (path.includes('/source')) {
    const isReadme = path.includes('README.md')
    return {
      revision: sha,
      path: isReadme ? 'README.md' : 'desktop/app/src/main/kotlin/Main.kt',
      content: isReadme ? '# Limingjie Repo\nClean local Git hub' : 'line1\n<script>unsafe</script>\n'.repeat(12),
    }
  }
  if (path.includes('/overview/generate')) {
    return { ...sampleOverview, sourceMode: 'llm', modelName: llmCfg.model, headline: 'AI 重新提炼后的架构摘要' }
  }
  if (path.includes('/overview')) return sampleOverview
  if (path === '/projects/1/notes' && method === 'GET') return savedNotes
  if (path === '/projects/1/notes' && method === 'POST') {
    const note: MaintenanceNote = {
      id: savedNotes.length + 1, project_id: 1, author_id: 1, author_username: actor?.username || 'dev',
      target_type: body.target_type, target_key: body.target_key, target_label: body.target_label,
      kind: body.kind, title: body.title, content: body.content, resolved: false, created_at: 10,
    }
    savedNotes = [note, ...savedNotes]
    return note
  }
  if (path.startsWith('/projects/1/notes/') && method === 'PATCH') {
    const id = Number(path.split('/').pop())
    savedNotes = savedNotes.map(n => n.id === id ? { ...n, resolved: body.resolved } : n)
    return savedNotes.find(n => n.id === id)
  }
  if (path.startsWith('/projects/1/notes/') && method === 'DELETE') {
    const id = Number(path.split('/').pop())
    savedNotes = savedNotes.filter(n => n.id !== id)
    return undefined
  }
  if (path === '/projects/1/ask') {
    return {
      mode: llmCfg.configured ? 'llm' : 'heuristic',
      model: llmCfg.model,
      answer: `关于「${body.question}」的结论。`,
      keyPoints: ['总控调度触发'],
      anchors: [{ path: 'desktop/app/src/main/kotlin/Main.kt', line: 12, end: 18, label: '同步入口' }],
    }
  }
  if (path === '/projects/1/analyses' && method === 'GET') return savedAnalyses
  if (path === '/projects/1/analyses' && method === 'POST') {
    currentDetail = { ...sampleAnalysisDetail, title: body.title, task_type: body.task_type }
    savedAnalyses = [currentDetail]
    return currentDetail
  }
  if (path === '/projects/1/analyses/10/explain') {
    currentDetail = {
      ...currentDetail, llm_status: 'generated',
      result: { ...currentDetail.result, plainSummary: { ...currentDetail.result.plainSummary, mode: 'llm', model: llmCfg.model, headline: 'AI 深度审阅摘要' } },
    }
    return currentDetail
  }
  if (path === '/projects/1/analyses/10/reviews' && method === 'POST') {
    const rec = {
      id: 1, task_id: 10, author_id: 2, author_username: 'review',
      verdict: body.verdict, comment: body.comment, test_status: body.test_status, test_notes: body.test_notes, created_at: 200,
    }
    currentDetail = { ...currentDetail, review_count: 1, latest_verdict: body.verdict, reviews: [rec] }
    savedAnalyses = [{ ...currentDetail }]
    return rec
  }
  if (path === '/projects/1/analyses/10') return currentDetail
  throw new Error(`Unexpected route: ${method} ${path}`)
}

async function render() {
  wrapper = mount(App)
  await flushPromises()
  return wrapper
}

function button(text: string) {
  const found = wrapper!.findAll('button').find(b => b.text().includes(text))
  if (!found) throw new Error(`Button not found: ${text}`)
  return found
}

beforeEach(() => {
  actor = null
  savedProjects = [{ ...baseProject }]
  savedNotes = [{
    id: 1, project_id: 1, author_id: 1, author_username: 'dev',
    target_type: 'module', target_key: 'app', target_label: '桌面界面与总控中枢',
    kind: 'pitfall', title: '跨事务状态注意', content: '取消任务检查会话清理', resolved: false, created_at: 1,
  }]
  currentDetail = structuredClone(sampleAnalysisDetail)
  savedAnalyses = [currentDetail]
  gitSt = {
    branch: 'main', head_sha: sha, clean: false,
    staged: [], unstaged: [{ path: 'desktop/app/src/main/kotlin/Main.kt', status: 'modified' }], untracked: [],
  }
  llmCfg = {
    provider: 'openai_compatible', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat',
    configured: false, masked_key: '',
    presets: [{ id: 'deepseek', label: 'DeepSeek', provider: 'openai_compatible', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' }],
  }
  mockApi.mockReset()
  mockApi.mockImplementation(handler as typeof api)
})

afterEach(() => wrapper?.unmount())

it('logs in, browses GitHub-style compact directory tree, README, and XSS-safe code viewer', async () => {
  await render()
  await wrapper!.get('input[name=username]').setValue('dev')
  await wrapper!.get('input[name=password]').setValue('password')
  await wrapper!.get('form').trigger('submit')
  await flushPromises()

  expect(wrapper!.text()).toContain('LimingjieDesktop')
  expect(wrapper!.text()).toContain('Clean local Git hub')
  expect(wrapper!.text()).toContain('1 处未提交变更')

  // Navigate into folder with automatic single-child path folding
  await button('desktop').trigger('click')
  expect(wrapper!.text()).toContain('app/src/main/kotlin')
  await button('app/src/main/kotlin').trigger('click')
  await button('Main.kt').trigger('click')
  await flushPromises()

  expect(wrapper!.get('pre').text()).toContain('<script>unsafe</script>')
  expect(wrapper!.find('pre script').exists()).toBe(false)
  await button('返回目录').trigger('click')

  // Quick file search
  await wrapper!.get('input[name=fileSearch]').setValue('Adb')
  expect(wrapper!.text()).toContain('desktop/device/Adb.kt')

  await button('退出').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('登录本地代码工作台')
})

it('operates local Git workspace: diffs, stages, commits, and inspects commit history', async () => {
  actor = developer
  await render()

  await button('1 处未提交变更').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('+newLine')

  // Stage all, write commit message, and commit
  await button('全部暂存').trigger('click')
  await flushPromises()
  await wrapper!.get('textarea[name=commitMessage]').setValue('feat: sync account projection')
  await wrapper!.get('.git-commit-box').trigger('submit')
  await flushPromises()

  expect(wrapper!.text()).toContain('Detailed body')
  await button('上一页').exists()
  await button('源码').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('Main.kt')
})

it('renders SVG architecture topology, drills into inspector drawer, configures AI, and rewrites overview', async () => {
  actor = developer
  await render()

  await button('架构导览').trigger('click')
  await flushPromises()
  expect(wrapper!.find('svg.topology-svg').exists()).toBe(true)
  expect(wrapper!.text()).toContain('启动前准备共享账号')

  // Filter SVG node and reset
  await wrapper!.find('g.svg-node').trigger('click')
  await button('重置筛选').trigger('click')

  // Drill into pipeline step -> ContextDrawer -> Q&A + Note + Anchor jump
  await wrapper!.find('.pipeline-step').trigger('click')
  await wrapper!.find('.inspector-drawer .chip-btn').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('总控调度触发')

  await button('+ 便签').trigger('click')
  await wrapper!.get('input[name=noteTitle]').setValue('注意投影顺序')
  await wrapper!.get('textarea[name=noteContent]').setValue('先写库再改会话')
  await wrapper!.get('.inspector-drawer form').trigger('submit')
  await flushPromises()
  expect(savedNotes.length).toBe(2)

  // Configure AI settings and regenerate overview
  await button('AI 接口').trigger('click')
  await button('DeepSeek').trigger('click')
  await wrapper!.get('input[name=llmApiKey]').setValue('sk-1234567890')
  await button('测试连接').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('连接正常')
  await wrapper!.get('.modal-panel form').trigger('submit')
  await flushPromises()
  await wrapper!.get('[aria-label="关闭模型设置"]').trigger('click')

  await button('AI 重新提炼').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('AI 重新提炼后的架构摘要')
})

it('runs impact review, AI deep review, reviewer sign-off, and maintenance Q&A/notes', async () => {
  actor = developer
  llmCfg.configured = true
  await render()

  // Edit project settings inline
  await button('设置').trigger('click')
  await wrapper!.get('input[name=editProjectName]').setValue('Limingjie Core')
  await wrapper!.get('form.edit-inline').trigger('submit')
  await flushPromises()
  expect(wrapper!.text()).toContain('Limingjie Core')

  // Impact Review tab
  await button('影响审阅').trigger('click')
  await flushPromises()
  await button('对比工作区').trigger('click')
  await wrapper!.get('form.form-panel').trigger('submit')
  await flushPromises()
  await button('AI 深度解读').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('AI 深度审阅摘要')

  // Maintenance & Q&A tab
  await button('问答与便签').trigger('click')
  await flushPromises()
  await wrapper!.find('.prompt-chips .chip-btn').trigger('click')
  await flushPromises()
  expect(wrapper!.text()).toContain('总控调度触发')

  await button('新建').trigger('click')
  await wrapper!.get('input[name=noteTitleMain]').setValue('拆分识别器')
  await wrapper!.get('textarea[name=noteContentMain]').setValue('按页面拆分')
  await wrapper!.get('form.form-panel').trigger('submit')
  await flushPromises()
  await button('完成').trigger('click')
  await flushPromises()

  // Reviewer sign-off flow
  wrapper!.unmount()
  actor = reviewer
  await render()
  await button('影响审阅').trigger('click')
  await flushPromises()
  await wrapper!.get('select[name=reviewVerdict]').setValue('approved')
  await wrapper!.get('select[name=testStatus]').setValue('passed')
  await wrapper!.get('input[name=reviewComment]').setValue('逻辑核对无误')
  await wrapper!.get('input[name=testNotes]').setValue('集成测试通过')
  await wrapper!.get('form.form-panel').trigger('submit')
  await flushPromises()
  expect(wrapper!.text()).toContain('逻辑核对无误')
})

it('handles onboarding new repo, login error alert, and 401 session expiry', async () => {
  mockApi.mockImplementation((async (path, method, body) => {
    if (path === '/auth/login') throw new ApiError(401, '密码错误')
    return handler(path, method, body)
  }) as typeof api)
  await render()
  await wrapper!.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper!.get('[role=alert]').text()).toContain('密码错误')
  await wrapper!.get('[aria-label="关闭提示"]').trigger('click')
  wrapper!.unmount()

  actor = developer
  savedProjects = []
  mockApi.mockImplementation(handler as typeof api)
  await render()
  await button('+ 接入本地仓库').trigger('click')
  await wrapper!.get('input[name=projectName]').setValue('FreshRepo')
  await wrapper!.get('input[name=repositoryPath]').setValue('D:/Project/LimingjieDesktop')
  await wrapper!.get('form.form-panel').trigger('submit')
  await flushPromises()
  expect(wrapper!.text()).toContain('FreshRepo')
})
