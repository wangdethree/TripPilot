import { useEffect, useMemo, useState } from "react";
import {
  addMessage,
  cancelTask,
  confirmTask,
  createTask,
  getResult,
  getTask,
  savePlan
} from "./api";
import type {
  ConstraintResult,
  TaskStatus,
  TaskView,
  TimelineItem,
  TripPlan
} from "./types";

const STATUS_LABELS: Record<TaskStatus, string> = {
  COLLECTING_REQUIREMENTS: "补充需求",
  AWAITING_CONFIRMATION: "确认需求",
  PLANNING: "生成行程",
  REPLANNING: "修正规划",
  COMPLETED: "规划完成",
  PARTIAL: "部分完成",
  NEEDS_USER_INPUT: "需要决策",
  FAILED: "规划失败",
  CANCELLED: "已取消"
};

const FIELD_LABELS: Record<string, string> = {
  destination_city: "目的地城市",
  start_date: "开始日期",
  end_date_or_days: "结束日期或天数",
  traveler_count: "同行人数",
  budget_total: "总预算",
  budget_includes_accommodation: "预算是否包含住宿",
  interests: "兴趣偏好"
};

const ITEM_LABELS: Record<TimelineItem["item_type"], string> = {
  ACTIVITY: "游览",
  TRANSIT: "交通",
  MEAL: "用餐",
  REST: "休息"
};

function futureDate(): string {
  const value = new Date();
  value.setDate(value.getDate() + 90);
  return value.toISOString().slice(0, 10);
}

function App() {
  const [description, setDescription] = useState(
    `${futureDate()} 去成都玩两天，两个人，预算 3000 元，不包含住宿，喜欢历史和美食，节奏轻松`
  );
  const [taskToken, setTaskToken] = useState<string | null>(null);
  const [task, setTask] = useState<TaskView | null>(null);
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [supplement, setSupplement] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const isRunning =
    task?.status === "PLANNING" || task?.status === "REPLANNING";

  useEffect(() => {
    if (!taskToken || !isRunning) return;
    let active = true;
    const poll = window.setInterval(async () => {
      try {
        const latest = await getTask(taskToken);
        if (!active) return;
        setTask(latest);
        if (latest.result_available) {
          const result = await getResult(taskToken);
          if (active) setPlan(result);
        }
      } catch (caught) {
        if (active) setError(messageOf(caught));
      }
    }, 900);
    return () => {
      active = false;
      window.clearInterval(poll);
    };
  }, [taskToken, isRunning]);

  const progressIndex = useMemo(() => {
    if (!task) return 0;
    if (task.status === "COLLECTING_REQUIREMENTS") return 0;
    if (task.status === "AWAITING_CONFIRMATION") return 1;
    if (task.status === "PLANNING" || task.status === "REPLANNING") return 2;
    return 3;
  }, [task]);

  async function begin() {
    setBusy(true);
    setError("");
    setPlan(null);
    try {
      const created = await createTask(description);
      setTaskToken(created.task_token);
      setTask(await getTask(created.task_token));
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submitSupplement() {
    if (!taskToken || !task || !supplement.trim()) return;
    setBusy(true);
    setError("");
    try {
      await addMessage(taskToken, task.row_version, supplement);
      setTask(await getTask(taskToken));
      setSupplement("");
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!taskToken || !task) return;
    setBusy(true);
    setError("");
    try {
      await confirmTask(taskToken, task.row_version);
      setTask(await getTask(taskToken));
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!taskToken) return;
    await cancelTask(taskToken);
    setTask(await getTask(taskToken));
  }

  async function save() {
    if (!taskToken) return;
    setBusy(true);
    try {
      const saved = await savePlan(taskToken);
      const share = `${window.location.origin}${window.location.pathname}#plan=${saved.plan_token}`;
      await navigator.clipboard?.writeText(share);
      setSavedMessage(`分享链接已复制，行程保留至 ${formatDate(saved.expires_at)}`);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setTaskToken(null);
    setTask(null);
    setPlan(null);
    setError("");
    setSavedMessage("");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="TripPilot 首页">
          <span className="brand-mark">TP</span>
          <span>TripPilot</span>
        </a>
        <div className="mode-pill">
          <span className="pulse-dot" />
          可控规划模式
        </div>
      </header>

      <main>
        {!task ? (
          <section className="hero">
            <div className="eyebrow">TRAVEL PLANNING AGENT · 可信行程实验室</div>
            <h1>
              不只给灵感，
              <br />
              还替你把行程<span>检查一遍。</span>
            </h1>
            <p className="hero-copy">
              用一句话说清目的地、日期、人数与偏好。TripPilot 会查找候选地点，
              生成每日时间线，并确定性检查预算、路线和活动强度。
            </p>

            <div className="composer">
              <label htmlFor="trip-description">描述你的旅行</label>
              <textarea
                id="trip-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={4}
                placeholder="例如：十月去成都玩三天，两个人，预算三千……"
              />
              <div className="composer-footer">
                <div className="trust-note">
                  <span>✓</span> 规划前确认需求 · 最多自动修正 2 次
                </div>
                <button className="primary-button" onClick={begin} disabled={busy}>
                  {busy ? "正在理解…" : "开始规划"}
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>

            <div className="feature-strip">
              <Feature number="01" title="先确认，再规划" text="默认值和歧义不会被悄悄带过" />
              <Feature number="02" title="证据驱动" text="地点与动态信息都保留来源记录" />
              <Feature number="03" title="规则兜底" text="模型不能决定自己是否规划成功" />
            </div>
          </section>
        ) : (
          <section className="workspace">
            <div className="workspace-heading">
              <div>
                <div className="eyebrow">PLANNING WORKSPACE</div>
                <h2>{destinationOf(task)} · 行程工作台</h2>
              </div>
              <button className="text-button" onClick={reset}>
                重新开始
              </button>
            </div>

            <Progress current={progressIndex} />
            {error && <div className="alert error-alert">{error}</div>}

            {task.status === "COLLECTING_REQUIREMENTS" && (
              <section className="panel split-panel">
                <div>
                  <span className="panel-kicker">还差一点</span>
                  <h3>补充必要信息</h3>
                  <p>为了让约束检查有明确依据，以下信息需要由你确认：</p>
                  <div className="missing-list">
                    {task.missing_fields.map((field) => (
                      <span key={field}>{FIELD_LABELS[field] ?? field}</span>
                    ))}
                  </div>
                </div>
                <div className="supplement-box">
                  <label htmlFor="supplement">直接用自然语言补充</label>
                  <textarea
                    id="supplement"
                    value={supplement}
                    onChange={(event) => setSupplement(event.target.value)}
                    placeholder="例如：预算不包含住宿，喜欢历史和美食"
                    rows={4}
                  />
                  <button
                    className="primary-button"
                    onClick={submitSupplement}
                    disabled={busy || !supplement.trim()}
                  >
                    提交补充
                  </button>
                </div>
              </section>
            )}

            {task.status === "AWAITING_CONFIRMATION" && (
              <section className="panel">
                <span className="panel-kicker">规划前检查点</span>
                <h3>确认这份旅行需求</h3>
                <p>确认后才会查询旅行数据并生成正式行程。</p>
                <SummaryGrid summary={task.request_summary} />
                {task.assumptions.length > 0 && (
                  <div className="assumption-box">
                    <strong>本次显式默认值</strong>
                    {task.assumptions.map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                )}
                <div className="action-row">
                  <button className="secondary-button" onClick={reset}>
                    返回修改
                  </button>
                  <button className="primary-button" onClick={confirm} disabled={busy}>
                    确认并生成行程 <span aria-hidden="true">→</span>
                  </button>
                </div>
              </section>
            )}

            {isRunning && (
              <section className="planning-stage" aria-live="polite">
                <div className="orbit">
                  <div className="orbit-core">TP</div>
                </div>
                <span className="panel-kicker">AGENT 正在工作</span>
                <h3>{task.status === "REPLANNING" ? "正在根据失败证据修正" : "正在组合可信候选"}</h3>
                <p>{workflowCopy(task.workflow_step)}</p>
                <div className="planning-facts">
                  <span>天气与地点并发查询</span>
                  <span>候选 #{Math.max(task.attempt_number, 1)}</span>
                  <span>硬约束由程序检查</span>
                </div>
                <button className="text-button danger" onClick={cancel}>
                  取消规划
                </button>
              </section>
            )}

            {plan && (
              <PlanView plan={plan} onSave={save} busy={busy} savedMessage={savedMessage} />
            )}

            {["FAILED", "NEEDS_USER_INPUT", "CANCELLED"].includes(task.status) && (
              <section className="panel terminal-panel">
                <span className="panel-kicker">{STATUS_LABELS[task.status]}</span>
                <h3>这次没有发布不可靠的行程</h3>
                <p>系统已按受控终止规则停止。你可以调整预算、日期或必去地点后重新开始。</p>
                <button className="primary-button" onClick={reset}>
                  创建新任务
                </button>
              </section>
            )}
          </section>
        )}
      </main>

      <footer>
        <span>TripPilot · 旅行建议需在出发前复核动态信息</span>
        <span>Agent workflow / deterministic guardrails / source records</span>
      </footer>
    </div>
  );
}

function Feature({ number, title, text }: { number: string; title: string; text: string }) {
  return (
    <div className="feature">
      <span>{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
}

function Progress({ current }: { current: number }) {
  const steps = ["理解需求", "确认边界", "生成与校验", "交付行程"];
  return (
    <ol className="progress" aria-label="规划进度">
      {steps.map((step, index) => (
        <li className={index <= current ? "active" : ""} key={step}>
          <span>{index < current ? "✓" : index + 1}</span>
          {step}
        </li>
      ))}
    </ol>
  );
}

function SummaryGrid({ summary }: { summary: Record<string, unknown> }) {
  const rows: Array<[string, unknown]> = [
    ["目的地", summary.destination_city],
    ["日期", dateRangeOf(summary.date_range)],
    ["同行人数", `${String(summary.traveler_count)} 人`],
    ["总预算", `¥${moneyOf(summary.budget_total)}`],
    ["住宿口径", summary.budget_includes_accommodation ? "包含住宿" : "住宿另算"],
    ["兴趣", arrayOf(summary.interests).join(" · ")],
    ["旅行节奏", paceLabel(String(summary.pace ?? ""))],
    ["每日时间", `${String(summary.daily_start_time).slice(0, 5)}–${String(summary.daily_end_time).slice(0, 5)}`]
  ];
  return (
    <div className="summary-grid">
      {rows.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{String(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function PlanView({
  plan,
  onSave,
  busy,
  savedMessage
}: {
  plan: TripPlan;
  onSave: () => void;
  busy: boolean;
  savedMessage: string;
}) {
  const notableChecks = plan.constraint_results.filter((check) => check.status !== "PASS");
  const passCount = plan.constraint_results.filter((check) => check.status === "PASS").length;
  return (
    <div className="plan-layout">
      <section className="plan-main">
        <div className="result-hero">
          <div>
            <span className={`status-badge ${plan.status.toLowerCase()}`}>
              {plan.status === "COMPLETED" ? "已通过硬约束检查" : "存在待确认信息"}
            </span>
            <h3>{plan.request_snapshot.destination_city} · {plan.days.length} 日行程</h3>
            <p>
              为 {plan.request_snapshot.traveler_count} 位旅行者生成，重点覆盖
              {plan.request_snapshot.interests.join("、")}。
            </p>
          </div>
          <button className="primary-button" onClick={onSave} disabled={busy}>
            保存并复制分享链接
          </button>
        </div>
        {savedMessage && <div className="alert success-alert">{savedMessage}</div>}

        {plan.days.map((day, dayIndex) => (
          <article className="day-card" key={day.date}>
            <div className="day-heading">
              <span>DAY {String(dayIndex + 1).padStart(2, "0")}</span>
              <div>
                <h4>{day.theme}</h4>
                <p>{formatDate(day.date)}</p>
              </div>
            </div>
            <div className="timeline">
              {day.timeline_items.map((item) => (
                <div className="timeline-item" key={item.item_id}>
                  <time>{item.start_time.slice(0, 5)}</time>
                  <div className={`timeline-dot ${item.item_type.toLowerCase()}`} />
                  <div className="timeline-content">
                    <div className="item-topline">
                      <span>{ITEM_LABELS[item.item_type]}</span>
                      <span>
                        {item.estimated_cost.amount === null
                          ? "费用未知"
                          : `¥${item.estimated_cost.amount}`}
                      </span>
                    </div>
                    <h5>{item.title}</h5>
                    <p>{item.description}</p>
                    {item.warnings.map((warning) => (
                      <small key={warning}>提示：{warning}</small>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <aside className="plan-aside">
        <section className="metric-card">
          <span>预算范围内支出</span>
          <strong>¥{plan.budget_summary.budget_scope_total}</strong>
          <div className="budget-row">
            <span>剩余预算</span>
            <b>¥{plan.budget_summary.remaining_budget}</b>
          </div>
          <div className="budget-row">
            <span>建议预留</span>
            <b>¥{plan.budget_summary.reserve}</b>
          </div>
        </section>
        <section className="check-card">
          <div className="aside-title">
            <span>约束检查</span>
            <b>{passCount} 项通过</b>
          </div>
          {notableChecks.length === 0 ? (
            <p className="all-clear">✓ 没有需要额外处理的已知问题</p>
          ) : (
            notableChecks.map((check) => <Check key={check.constraint_id} check={check} />)
          )}
        </section>
        <section className="source-card">
          <div className="aside-title">
            <span>信息来源</span>
            <b>{plan.sources.length} 条</b>
          </div>
          {plan.sources.slice(0, 6).map((source) => (
            <div className="source-row" key={source.source_id}>
              <span className="source-icon">{source.freshness_status === "FRESH" ? "●" : "○"}</span>
              <div>
                <strong>{source.provider}</strong>
                <p>{source.title}</p>
              </div>
            </div>
          ))}
        </section>
      </aside>
    </div>
  );
}

function Check({ check }: { check: ConstraintResult }) {
  return (
    <div className={`check-row ${check.status.toLowerCase()}`}>
      <span>{check.status === "WARNING" ? "!" : check.status === "UNKNOWN" ? "?" : "×"}</span>
      <div>
        <strong>{check.status}</strong>
        <p>{check.message}</p>
      </div>
    </div>
  );
}

function destinationOf(task: TaskView): string {
  return String(task.request_summary.destination_city ?? "新旅行");
}

function workflowCopy(step: string | null): string {
  const copy: Record<string, string> = {
    load_planning_context: "正在并发查询天气和候选地点…",
    generate_candidate: "正在根据偏好组合每日活动…",
    enrich_candidate: "正在补全路线、费用与开放时间…",
    validate_candidate: "正在执行预算、时间与路线规则…",
    prepare_replan: "正在把失败证据反馈给下一轮候选…"
  };
  return copy[step ?? ""] ?? "正在运行有限状态工作流，请稍候…";
}

function dateRangeOf(value: unknown): string {
  if (!value || typeof value !== "object") return "—";
  const range = value as Record<string, unknown>;
  return `${String(range.start)} 至 ${String(range.end)}`;
}

function moneyOf(value: unknown): string {
  if (value && typeof value === "object" && "amount" in value) {
    return String((value as { amount: unknown }).amount);
  }
  return String(value ?? "—");
}

function arrayOf(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function paceLabel(value: string): string {
  return { relaxed: "轻松", moderate: "适中", intensive: "紧凑" }[value] ?? value;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric"
  }).format(new Date(value));
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "发生未知错误";
}

export default App;
