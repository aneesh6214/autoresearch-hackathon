export type Role = "student" | "tutor"

export interface ChatMessage {
  id: string
  role: Role
  content: string
  latencySeconds?: number
  modelCallCount?: number
  tokenUsage?: Record<string, number>
}

export interface TutorConfig {
  subject: string
  targetConcept: string
  tutoringGoal: string
}

export interface RunSummary {
  winner_candidate_id: string
  elapsed_seconds: number
  candidate_count: number
  passed_count: number
  rejected_count: number
  error_count: number
  phase_counts: Record<string, number>
  costs: Record<string, number>
  stop_reasons: string[]
}

export interface StrategySpec {
  candidate_id: string
  response_architecture: string
  tutor_policy: string
  output_structure: string
  hidden_planning_prompt: string | null
  rationale: string
  max_model_calls: number
}

export interface BenchmarkManifest {
  counts?: Record<string, unknown>
  sources?: Record<string, unknown>
}

export interface RunData {
  run_dir: string
  summary: RunSummary
  strategy: StrategySpec
  benchmark_manifest: BenchmarkManifest
}

export interface ChatResponse {
  reply: string
  candidate_id: string
  architecture: string
  model_call_count: number
  latency_seconds: number
  token_usage: Record<string, number>
}
