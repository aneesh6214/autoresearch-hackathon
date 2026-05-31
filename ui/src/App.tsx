import { FormEvent, useEffect, useMemo, useState } from "react"
import {
  Activity,
  Download,
  FileText,
  RotateCcw,
  Send,
  Settings2,
  Sparkles,
} from "lucide-react"

import type { ChatMessage, ChatResponse, RunData, TutorConfig } from "./types"

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8765"

const DEFAULT_CONFIG: TutorConfig = {
  subject: "math",
  targetConcept: "linear equations",
  tutoringGoal:
    "Use the optimized tutor strategy. Diagnose the student's current state, avoid answer dumping, and end with one concrete next question.",
}

const STARTERS: Array<{ label: string; subject: string; concept: string; message: string }> = [
  {
    label: "Algebra",
    subject: "math",
    concept: "linear equations",
    message: "I subtracted 7 from both sides and got 5x = 20. Can you just tell me x?",
  },
  {
    label: "Fractions",
    subject: "math",
    concept: "fraction addition",
    message: "I think 2/3 + 1/4 is 3/7 because I added the top and bottom.",
  },
  {
    label: "Physics",
    subject: "physics",
    concept: "Newton's laws",
    message: "Force is mass times velocity, right? My answer uses F = mv.",
  },
]

function App() {
  const [runData, setRunData] = useState<RunData | null>(null)
  const [config, setConfig] = useState<TutorConfig>(DEFAULT_CONFIG)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState<string>("")
  const [isSending, setIsSending] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string>("")

  useEffect(() => {
    void loadRunData()
  }, [])

  const canSend = draft.trim().length > 0 && !isSending
  const scoreDelta = useMemo(() => {
    if (!runData) return null
    return {
      cost: runData.summary.costs.estimated_openai_usd ?? 0,
      phases: runData.summary.phase_counts,
    }
  }, [runData])

  async function loadRunData(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/api/run`)
      if (!response.ok) throw new Error(`Run metadata request failed: ${response.status}`)
      setRunData((await response.json()) as RunData)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load run metadata.")
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!canSend) return

    const studentMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "student",
      content: draft.trim(),
    }
    const nextMessages = [...messages, studentMessage]
    setMessages(nextMessages)
    setDraft("")
    setIsSending(true)
    setErrorMessage("")

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMessages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
          config: {
            subject: config.subject,
            target_concept: config.targetConcept,
            tutoring_goal: config.tutoringGoal,
          },
        }),
      })
      if (!response.ok) throw new Error(`Tutor request failed: ${response.status}`)
      const data = (await response.json()) as ChatResponse
      setMessages([
        ...nextMessages,
        {
          id: crypto.randomUUID(),
          role: "tutor",
          content: data.reply,
          latencySeconds: data.latency_seconds,
          modelCallCount: data.model_call_count,
          tokenUsage: data.token_usage,
        },
      ])
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Tutor request failed.")
      setMessages(messages)
    } finally {
      setIsSending(false)
    }
  }

  function applyStarter(index: number): void {
    const starter = STARTERS[index]
    setConfig({
      ...config,
      subject: starter.subject,
      targetConcept: starter.concept,
    })
    setDraft(starter.message)
  }

  function resetSession(): void {
    setMessages([])
    setDraft("")
    setErrorMessage("")
  }

  function downloadReport(): void {
    const html = buildReportHtml({
      runData,
      config,
      messages,
      generatedAt: new Date(),
    })
    const blob = new Blob([html], { type: "text/html" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `tutor-report-${new Date().toISOString().replaceAll(":", "-")}.html`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="app-shell">
      <aside className="control-panel">
        <header className="panel-header">
          <div>
            <p className="eyebrow">Autoresearch Tutor</p>
            <h1>Ephemeral Test</h1>
          </div>
          <Sparkles size={20} />
        </header>

        <section className="panel-section">
          <div className="section-title">
            <Settings2 size={16} />
            <span>Pre-Test</span>
          </div>
          <label>
            Subject
            <input
              value={config.subject}
              onChange={(event) => setConfig({ ...config, subject: event.target.value })}
            />
          </label>
          <label>
            Target Concept
            <input
              value={config.targetConcept}
              onChange={(event) =>
                setConfig({ ...config, targetConcept: event.target.value })
              }
            />
          </label>
          <label>
            Tutor Goal
            <textarea
              value={config.tutoringGoal}
              rows={5}
              onChange={(event) =>
                setConfig({ ...config, tutoringGoal: event.target.value })
              }
            />
          </label>
          <div className="starter-row">
            {STARTERS.map((starter, index) => (
              <button
                key={starter.label}
                type="button"
                className="subtle-button"
                onClick={() => applyStarter(index)}
              >
                {starter.label}
              </button>
            ))}
          </div>
        </section>

        <section className="panel-section">
          <div className="section-title">
            <Activity size={16} />
            <span>Run</span>
          </div>
          <Metric label="Winner" value={runData?.summary.winner_candidate_id ?? "loading"} />
          <Metric
            label="Architecture"
            value={runData?.strategy.response_architecture ?? "loading"}
          />
          <Metric
            label="Candidates"
            value={String(runData?.summary.candidate_count ?? "loading")}
          />
          <Metric
            label="Estimated OpenAI"
            value={`$${scoreDelta ? scoreDelta.cost.toFixed(2) : "0.00"}`}
          />
        </section>

        <section className="panel-section strategy-section">
          <div className="section-title">
            <FileText size={16} />
            <span>Strategy</span>
          </div>
          <p>{runData?.strategy.output_structure ?? "Loading strategy."}</p>
        </section>
      </aside>

      <main className="chat-panel">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Manual Session</p>
            <h2>{config.targetConcept || "Untitled concept"}</h2>
          </div>
          <div className="toolbar">
            <button type="button" className="icon-button" onClick={resetSession} title="Reset">
              <RotateCcw size={18} />
            </button>
            <button
              type="button"
              className="download-button"
              onClick={downloadReport}
              title="Download report"
            >
              <Download size={18} />
              Report
            </button>
          </div>
        </header>

        <div className="message-list">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>No turns yet.</p>
            </div>
          ) : (
            messages.map((message) => <MessageBubble key={message.id} message={message} />)
          )}
          {isSending && <div className="thinking">Tutor is thinking...</div>}
        </div>

        {errorMessage && <div className="error-banner">{errorMessage}</div>}

        <form className="composer" onSubmit={(event) => void submitMessage(event)}>
          <textarea
            value={draft}
            rows={3}
            placeholder="Student message"
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" disabled={!canSend} title="Send">
            <Send size={18} />
          </button>
        </form>
      </main>
    </div>
  )
}

interface MetricProps {
  label: string
  value: string
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

interface MessageBubbleProps {
  message: ChatMessage
}

function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <article className={`message ${message.role}`}>
      <div className="message-role">{message.role === "student" ? "Student" : "Tutor"}</div>
      <p>{message.content}</p>
      {message.role === "tutor" && (
        <div className="message-meta">
          <span>{message.modelCallCount ?? 0} calls</span>
          <span>{(message.latencySeconds ?? 0).toFixed(1)}s</span>
          <span>{message.tokenUsage?.total_tokens ?? 0} tokens</span>
        </div>
      )}
    </article>
  )
}

interface ReportInput {
  runData: RunData | null
  config: TutorConfig
  messages: ChatMessage[]
  generatedAt: Date
}

function buildReportHtml(input: ReportInput): string {
  const run = input.runData
  const messageRows = input.messages
    .map(
      (message) => `
        <section class="turn ${message.role}">
          <div class="role">${escapeHtml(message.role)}</div>
          <p>${escapeHtml(message.content)}</p>
          ${
            message.role === "tutor"
              ? `<div class="meta">${message.modelCallCount ?? 0} calls · ${(message.latencySeconds ?? 0).toFixed(1)}s · ${message.tokenUsage?.total_tokens ?? 0} tokens</div>`
              : ""
          }
        </section>
      `,
    )
    .join("")
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Autoresearch Tutor Report</title>
  <style>
    body { margin: 0; background: #f4f5f7; color: #1b1f24; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 920px; margin: 0 auto; padding: 32px; }
    header { border-left: 5px solid #2f6f73; padding: 20px 24px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08); }
    h1 { margin: 0 0 6px; font-size: 28px; }
    h2 { margin: 28px 0 12px; font-size: 18px; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 18px; }
    .metric, .turn, .strategy { background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; }
    .metric span, .role, .meta { color: #5d6778; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .metric strong { display: block; margin-top: 4px; font-size: 16px; }
    .turn { margin-bottom: 10px; }
    .turn.student { border-left: 4px solid #446bb3; }
    .turn.tutor { border-left: 4px solid #2f6f73; }
    .meta { margin-top: 10px; text-transform: none; letter-spacing: 0; }
    pre { white-space: pre-wrap; background: #20242b; color: #f6f7f9; border-radius: 8px; padding: 16px; overflow: auto; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Autoresearch Tutor Session</h1>
      <div>Generated ${escapeHtml(input.generatedAt.toLocaleString())}</div>
      <div class="grid">
        <div class="metric"><span>Winner</span><strong>${escapeHtml(run?.summary.winner_candidate_id ?? "unknown")}</strong></div>
        <div class="metric"><span>Architecture</span><strong>${escapeHtml(run?.strategy.response_architecture ?? "unknown")}</strong></div>
        <div class="metric"><span>Subject</span><strong>${escapeHtml(input.config.subject)}</strong></div>
        <div class="metric"><span>Turns</span><strong>${input.messages.length}</strong></div>
      </div>
    </header>
    <h2>Session Transcript</h2>
    ${messageRows || '<section class="turn"><p>No chat turns recorded.</p></section>'}
    <h2>Configuration</h2>
    <section class="strategy">
      <p><strong>Target concept:</strong> ${escapeHtml(input.config.targetConcept)}</p>
      <p><strong>Tutor goal:</strong> ${escapeHtml(input.config.tutoringGoal)}</p>
    </section>
    <h2>Optimized Strategy</h2>
    <pre>${escapeHtml(JSON.stringify(run?.strategy ?? {}, null, 2))}</pre>
    <h2>Run Summary</h2>
    <pre>${escapeHtml(JSON.stringify(run?.summary ?? {}, null, 2))}</pre>
  </main>
</body>
</html>`
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}

export default App
