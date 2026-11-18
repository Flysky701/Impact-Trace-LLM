export interface User { id: number; username: string; role: 'developer' | 'reviewer' }

export interface Project {
  id: number; name: string; description: string; repository_path: string;
  owner_id: number; reviewer_id: number | null; created_at: number;
}

export interface BranchRef {
  name: string; sha: string; short_sha: string; date: string; subject: string; current: boolean;
}

export interface TagRef {
  name: string; short_sha: string; date: string;
}

export interface RepoRefs {
  current_branch: string; head_sha: string; branches: BranchRef[]; tags: TagRef[];
}

export interface Commit {
  sha: string; short_sha: string; author?: string; date: string; subject: string;
}

export interface History { revision: string; total: number; commits: Commit[] }
export interface Tree { revision: string; files: { path: string; oid: string }[]; truncated: boolean }
export interface Source { revision: string; path: string; content: string }

export interface FileChange {
  path: string; status: 'added' | 'modified' | 'deleted' | 'renamed' | 'untracked';
  additions: number; deletions: number; diff: string;
}

export interface CommitDetail {
  sha: string; short_sha: string; author: string; email: string; date: string;
  parents: string[]; subject: string; body: string;
  files: FileChange[];
  stats: { files: number; additions: number; deletions: number };
}

export interface GitStatusEntry {
  path: string; status: 'added' | 'modified' | 'deleted' | 'renamed' | 'untracked';
}

export interface GitStatus {
  branch: string; head_sha: string; clean: boolean;
  staged: GitStatusEntry[]; unstaged: GitStatusEntry[]; untracked: GitStatusEntry[];
}

export interface Anchor {
  path: string; line: number; end?: number; label: string;
}

export interface RoleBlock {
  id: string; title: string; subtitle: string; plainHow: string;
  fileCount: number; lineCount: number; anchors: Anchor[];
}

export interface RoleFlow {
  from: string; to: string; action: string; detail: string;
}

export interface FlowStep {
  stepNo: number; what: string; why: string; howPlain: string;
  moduleId: string; anchors: Anchor[];
  changeTag?: 'unchanged' | 'modified' | 'added' | 'deleted';
}

export interface Storyline {
  id: string; title: string; when: string; outcome: string; steps: FlowStep[];
}

export interface DataCard {
  id: string; plainName: string; rawName: string; purpose: string;
  fieldCount: number; relations: string[]; anchors: Anchor[];
}

export interface Hotspot {
  id: string; title: string; whyHard: string; splitIdea: string;
  severity: 'high' | 'medium' | 'low'; metrics: string; moduleId: string; anchors: Anchor[];
}

export interface RepoOverview {
  repoName: string; revision: string; commit: string; language: string;
  sourceMode: 'heuristic' | 'llm'; modelName: string;
  headline: string; narrative: string;
  roles: RoleBlock[]; roleFlows: RoleFlow[]; storylines: Storyline[];
  dataCards: DataCard[]; hotspots: Hotspot[];
  stats: {
    files: number; lines: number; functions: number; classes: number;
    testFiles: number; parseErrorFiles: number;
  };
}

export interface LlmPreset {
  id: string; label: string; provider: string; base_url: string; model: string;
}

export interface LlmSettings {
  provider: string; base_url: string; model: string;
  configured: boolean; masked_key: string; presets: LlmPreset[];
}

export interface FlowComparison {
  id: string; plainTitle: string; symbolName: string; moduleId: string;
  status: 'modified' | 'added' | 'deleted'; path: string;
  beforeSteps: FlowStep[]; afterSteps: FlowStep[];
}

export interface ImpactItem {
  id: string; plainName: string; symbolName: string; moduleId: string;
  distance: number; alsoChanged: boolean; chain: string; reason: string;
  anchor: Anchor;
}

export interface ReviewRecord {
  id: number; task_id: number; author_id: number; author_username: string;
  verdict: 'approved' | 'attention' | 'needs_work';
  comment: string;
  test_status: 'not_run' | 'passed' | 'failed' | 'blocked';
  test_notes: string; created_at: number;
}

export interface AnalysisSummary {
  id: number; project_id: number; created_by: number;
  task_type: 'commit_compare' | 'ai_change';
  title: string; user_prompt: string;
  base_ref: string; head_ref: string; base_sha: string; head_sha: string;
  status: 'completed' | 'partial';
  llm_status: 'not_requested' | 'not_configured' | 'generated' | 'failed';
  headline: string;
  diagnostics: {
    changedFileCount: number; changedFlowCount: number;
    impactCount: number; parseErrorFiles: number;
  };
  review_count: number;
  latest_verdict: 'approved' | 'attention' | 'needs_work' | null;
  created_at: number;
}

export interface AnalysisDetail extends AnalysisSummary {
  raw_log: string;
  result: {
    baseSha: string; headSha: string; headCommit: string; language: string;
    plainSummary: {
      mode: string; model: string; headline: string; beforeVsAfter: string;
      riskPoints: { title: string; detail: string; anchors: Anchor[] }[];
      testSuggestions: string[];
      llmError?: string;
    };
    flowComparisons: FlowComparison[];
    impactRadius: ImpactItem[];
    fileChanges: FileChange[];
    diagnostics: AnalysisSummary['diagnostics'];
  };
  reviews: ReviewRecord[];
}

export interface MaintenanceNote {
  id: number; project_id: number; author_id: number; author_username: string;
  target_type: 'module' | 'flow' | 'file' | 'symbol';
  target_key: string; target_label: string;
  kind: 'pitfall' | 'refactor' | 'note';
  title: string; content: string; resolved: boolean; created_at: number;
}

export interface AskResponse {
  mode: 'heuristic' | 'llm'; model: string;
  answer: string; keyPoints: string[]; anchors: Anchor[];
}

export interface DrawerFocus {
  title: string;
  subtitle: string;
  howPlain: string;
  targetType: 'module' | 'flow' | 'file' | 'symbol';
  targetKey: string;
  revision: string;
  anchors: Anchor[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api' + path, {
      method, credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'ImpactTrace' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch { throw new ApiError(0, '无法连接服务，请检查后端是否正在运行。') }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : '请求未完成，请检查输入后重试。')
  }
  return response.status === 204 ? undefined as T : response.json()
}
