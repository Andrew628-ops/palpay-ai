import { useEffect, useRef, useState } from "react";
import Icon from "./components/Icon";
import CreateSmartPayForm from "./components/CreateSmartPayForm";
import AgreementPipeline from "./components/AgreementPipeline";
import SelectedAgreement from "./components/SelectedAgreement";
import GuidedDemo from "./components/GuidedDemo";
import PaymentHistory from "./components/PaymentHistory";
import DashboardAnalytics from "./components/DashboardAnalytics";
import RecentPaymentActivity from "./components/RecentPaymentActivity";
import ReviewQueue from "./components/ReviewQueue";
import { money, readResponse, statusLabel } from "./lib/format";
import "./App.css";

const PAGES = {
  dashboard: { label: "Command Center", icon: "grid", title: "Good things happen when trust comes first.", description: "Your agreements, evidence, and payments. All working together." },
  agreements: { label: "Agreements", icon: "file", title: "Every promise, in one place.", description: "Follow your agreements from agreed outcome to confirmed payment." },
  payments: { label: "Payments", icon: "arrows", title: "A clear view of every payment.", description: "Review your actual PayPal Sandbox payout records and analytics." },
  reviews: { label: "Trust & Evidence", icon: "shield", title: "A little intelligence. A lot of clarity.", description: "Review the evidence, understand the recommendation, and decide what happens next." },
};

function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [rules, setRules] = useState([]);
  const [connection, setConnection] = useState("loading");
  const [refreshKey, setRefreshKey] = useState(0);
  const [ruleId, setRuleId] = useState("");
  const [rule, setRule] = useState(null);
  const [loadingRule, setLoadingRule] = useState(false);
  const [error, setError] = useState("");
  const [demoOpen, setDemoOpen] = useState(false);
  const [activity, setActivity] = useState([]);
  const selectionRequest = useRef(0);
  const version = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const startedAt = version.current;
    fetch("/api/rules/smartpay", { signal: controller.signal, cache: "no-store" })
      .then(readResponse)
      .then(data => {
        if (!Array.isArray(data) || !data.every(item => Number.isInteger(item.id) && typeof item.status === "string" && Number.isFinite(Number(item.amount)))) throw new Error("Unexpected agreements response");
        if (controller.signal.aborted) return;
        if (startedAt === version.current) setRules(data);
        setConnection("connected");
      })
      .catch(err => { if (err.name !== "AbortError" && !controller.signal.aborted) setConnection("offline"); });
    return () => controller.abort();
  }, [refreshKey]);

  function retryConnection() { setConnection("loading"); setRefreshKey(value => value + 1); }
  function upsert(updated) {
    version.current += 1;
    setRules(previous => [...previous.filter(item => item.id !== updated.id), updated]);
    setConnection("connected");
  }
  function addActivity(title, detail, icon = "file") {
    setActivity(previous => [{ id: crypto.randomUUID(), title, detail, icon, time: new Date() }, ...previous].slice(0, 5));
  }
  function navigate(page) { setActivePage(page); setError(""); }
  function startAgreement() {
    navigate("dashboard");
    window.setTimeout(() => { document.getElementById("create-agreement")?.scrollIntoView({ behavior: "smooth", block: "center" }); document.getElementById("condition")?.focus({ preventScroll: true }); }, 50);
  }
  function revealSelection() { window.setTimeout(() => document.getElementById("selected-agreement")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50); }
  function selectRule(selected) {
    selectionRequest.current += 1;
    setRule(selected);
    setRuleId(String(selected.id));
    setLoadingRule(false);
    setError("");
    revealSelection();
  }
  async function refreshRule(id) {
    const data = await readResponse(await fetch(`/api/rules/smartpay/${id}`, { cache: "no-store" }));
    upsert(data);
    setRule(current => current?.id === data.id ? data : current);
    addActivity("Agreement updated", `#${data.id} · ${statusLabel(data.status)}`, data.status === "PAID" ? "check" : "pulse");
    return data;
  }
  async function lookup(id) {
    const request = ++selectionRequest.current;
    setError("");
    setLoadingRule(true);
    try {
      const data = await readResponse(await fetch(`/api/rules/smartpay/${id}`, { cache: "no-store" }));
      if (request !== selectionRequest.current) return;
      upsert(data);
      setRule(data);
      setRuleId(String(data.id));
      revealSelection();
    } catch (err) { if (request === selectionRequest.current) setError(err.message); }
    finally { if (request === selectionRequest.current) setLoadingRule(false); }
  }

  const page = PAGES[activePage];
  const known = connection === "connected" || rules.length > 0;
  const approvalCount = rules.filter(item => item.status === "AWAITING_USER_APPROVAL").length;
  const metrics = [
    { label: "Total agreement value", value: money(rules.filter(item => item.currency === "USD").reduce((sum, item) => sum + Number(item.amount), 0)), detail: "Across USD agreements", icon: "wallet", tone: "blue" },
    { label: "Active agreements", value: rules.filter(item => !["PAID", "HUMAN_REJECTED"].includes(item.status)).length, detail: "From commitment to completion", icon: "file", tone: "blue" },
    { label: "AI-reviewed agreements", value: rules.filter(item => item.ai_confidence != null).length, detail: "Recommendations, ready to review", icon: "sparkles", tone: "success" },
    { label: "Awaiting your approval", value: approvalCount, detail: "Your decision makes the difference", icon: "clock", tone: "warning" },
  ];
  const recent = activity.length ? activity : [...rules].sort((a, b) => b.id - a.id).slice(0, 4).map(item => ({ id: item.id, title: "Agreement created", detail: `${item.recipient_name} · ${money(item.amount, item.currency)}`, icon: "file", time: item.created_at ? new Date(item.created_at.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(item.created_at) ? item.created_at : `${item.created_at}Z`) : null }));
  const showWorkspace = ["dashboard", "agreements", "reviews"].includes(activePage);

  return <div className="app-layout">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#" onClick={event => { event.preventDefault(); navigate("dashboard"); }} aria-label="PalPay AI home"><span className="brand-mark"><Icon name="sparkles" size={24} /></span><span>PalPay<span className="brand-ai">AI</span></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <nav className="sidebar-nav" aria-label="Main navigation">{Object.entries(PAGES).map(([key, config]) => <button type="button" key={key} className={activePage === key ? "active" : ""} aria-current={activePage === key ? "page" : undefined} onClick={() => navigate(key)}><Icon name={config.icon} size={19} /><span>{config.label}</span>{key === "reviews" && approvalCount > 0 && <span className="nav-count">{approvalCount}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-story"><div className="story-icon"><Icon name="sparkles" size={22} /></div><strong>Big ideas.<br />Thoughtful payments.</strong><p>See how a promise becomes a payment.</p><button type="button" onClick={() => setDemoOpen(true)}>Explore the walkthrough<Icon name="arrow" size={15} /></button></div><button type="button" className={`settings-link ${activePage === "settings" ? "active" : ""}`} onClick={() => navigate("settings")} aria-current={activePage === "settings" ? "page" : undefined}><Icon name="settings" size={18} />Sandbox settings</button><div className="sidebar-profile"><span className="profile-avatar">P</span><span><strong>Hackathon workspace</strong><small><i />PayPal Sandbox</small></span><Icon name="chevron" size={15} /></div></div>
    </aside>
    <div className="workspace">
      <div className="topbar"><div className="breadcrumb">Workspace<Icon name="chevron" size={13} /><strong>{page?.label || "Settings"}</strong></div><div className="topbar-right"><span className="environment-pill"><i />SANDBOX</span><span className="topbar-divider" /><span className="powered-by">Payments with <strong>PayPal</strong></span><button type="button" className="icon-button topbar-action" aria-label="Refresh agreements" disabled={connection === "loading"} onClick={retryConnection}><Icon name="refresh" size={15} /></button><button type="button" className="icon-button topbar-action" aria-label="Workspace settings" onClick={() => navigate("settings")}><Icon name="settings" size={15} /></button></div></div>
      <main className="main-content" id="main-content">
        <header className="dashboard-header"><div><div className="eyebrow">{activePage === "dashboard" ? "YOUR INTELLIGENT PAYMENT WORKSPACE" : "PALPAY AI / " + (page?.label || "SETTINGS").toUpperCase()}</div><h1>{page?.title || "Built for your sandbox."}</h1><p>{page?.description || "Understand how your AI and PayPal integrations work together."}</p></div><button type="button" className="secondary-button walkthrough-button" onClick={() => setDemoOpen(true)}><Icon name="play" size={15} />Try the walkthrough</button></header>
        {connection === "offline" && <div className="connection-notice" role="status"><Icon name="info" size={18} /><span>The backend is unavailable. Start your API to load agreements, or explore the sample walkthrough.</span><button type="button" className="text-button" onClick={retryConnection}><Icon name="refresh" size={14} />Retry</button></div>}
        {activePage === "dashboard" && <>
          <section className="hero"><div className="hero-content"><span className="hero-eyebrow"><span className="hero-dot" />INTENT. EVIDENCE. PAYMENT.</span><h2>Pay for outcomes.<br /><span>Move forward with confidence.</span></h2><p>Agree on what success looks like. Let AI review the evidence.<br className="desktop-break" />You give the go-ahead. PayPal handles the payment.</p><button type="button" className="hero-cta" onClick={startAgreement}>Create an agreement<Icon name="arrow" size={16} /></button></div><div className="hero-visual" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="hero-spark spark-one">✦</div><div className="hero-spark spark-two">✦</div><div className="visual-node intent-node"><span className="node-icon"><Icon name="file" size={18} /></span><span><small>01 · YOUR INTENT</small><strong>A shared goal</strong></span><Icon name="check" size={15} /></div><div className="visual-node ai-node"><span className="node-icon"><Icon name="sparkles" size={20} /></span><span><small>02 · AI + YOU</small><strong>Evidence, understood.</strong></span></div><div className="visual-node pay-node"><span className="paypal-symbol">P</span><span><small>03 · PAYPAL</small><strong>Payment, with purpose.</strong></span><Icon name="shield" size={18} /></div></div></section>
          <div className="metrics-grid">{metrics.map(metric => <article className={`metric-card ${metric.tone}`} key={metric.label}><div className="metric-label">{metric.label}<Icon name={metric.icon} size={18} /></div><div className="metric-value">{known ? metric.value : "—"}</div><div className="metric-detail"><span className="metric-dot" />{metric.detail}</div></article>)}</div>
          <div className="dashboard-columns"><CreateSmartPayForm onCreated={created => { upsert(created); selectRule(created); addActivity("Agreement created", `${created.recipient_name} · ${money(created.amount, created.currency)}`); }} /><section className="panel activity-panel"><div className="panel-heading"><div><h2>Workspace activity</h2><p>A little context at every step.</p></div><span className={`activity-live ${connection === "connected" ? "connected" : ""}`}><i />{connection === "connected" ? "CONNECTED" : "WORKSPACE"}</span></div>{recent.length ? <ol className="activity-timeline">{recent.map(item => <li key={item.id}><span className="activity-event-icon"><Icon name={item.icon} size={15} /></span><div><strong>{item.title}</strong><p>{item.detail}</p><small>{item.time && !Number.isNaN(item.time.getTime()) ? item.time.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "Africa/Casablanca" }) : "Workspace update"}</small></div></li>)}</ol> : <div className="activity-empty"><span className="empty-icon"><Icon name="pulse" size={24} /></span><strong>Your story starts with an agreement.</strong><p>Creation and workflow updates appear here as you work.</p></div>}<div className="trust-note"><Icon name="shield" size={19} /><div><strong>Intelligence with a human touch.</strong><p>AI recommends. You authorize.<br />PayPal executes and confirms.</p></div></div></section></div>
        </>}
        {["dashboard", "agreements"].includes(activePage) && <AgreementPipeline rules={rules} loading={connection === "loading"} onSelect={selectRule} onCreate={startAgreement} expanded={activePage === "agreements"} />}
        {activePage === "reviews" && <><div className="trust-intro"><span className="heading-icon"><Icon name="shield" size={24} /></span><div><h2>Evidence you can examine. Decisions you can explain.</h2><p>Gemini assesses the submitted description against your agreement. Review its reasoning, request more evidence when needed, and keep a history of every decision.</p></div></div><ReviewQueue onSelectRule={id => { setRuleId(String(id)); lookup(id); }} /></>}
        {showWorkspace && <><section className="rule-lookup"><div><Icon name="search" size={18} /><span>Have an agreement ID?</span></div><form onSubmit={event => { event.preventDefault(); lookup(ruleId); }}><input type="number" min="1" step="1" required value={ruleId} onChange={event => setRuleId(event.target.value)} placeholder="Agreement ID" aria-label="Agreement ID" /><button type="submit" className="secondary-button" disabled={loadingRule}>{loadingRule ? "Opening…" : "Open agreement"}<Icon name="arrow" size={14} /></button></form></section>{error && <p className="error-message global-error" role="alert">{error}</p>}{rule && <SelectedAgreement key={rule.id} rule={rule} onRefresh={refreshRule} onError={setError} onClose={() => { selectionRequest.current += 1; setLoadingRule(false); setRule(null); }} />}</>}
        {activePage === "payments" && <div className="payments-page"><PaymentHistory /><DashboardAnalytics /><RecentPaymentActivity onViewAll={() => document.querySelector(".payment-history")?.scrollIntoView({ behavior: "smooth" })} /></div>}
        {activePage === "settings" && <div className="settings-grid"><section className="panel settings-panel"><span className="heading-icon"><Icon name="arrows" /></span><h2>PayPal Sandbox</h2><p>Test payouts use PayPal Sandbox accounts. Review the actual receiving account before authorizing each payout.</p><dl><div><dt>Environment</dt><dd><span className="status-badge blue">Sandbox only</span></dd></div><div><dt>Supported payouts</dt><dd>USD</dd></div><div><dt>Payment authorization</dt><dd>Operator approval required</dd></div></dl><a href="https://developer.paypal.com/docs/payouts/standard/" target="_blank" rel="noreferrer">PayPal Payouts documentation<Icon name="arrow" size={15} /></a></section><section className="panel settings-panel"><span className="heading-icon"><Icon name="sparkles" /></span><h2>Gemini AI review</h2><p>The live review uses your backend’s Gemini integration. Recommendations use the evidence description and your release condition.</p><div className="inline-note"><Icon name="info" size={17} /><p>The AI does not independently inspect linked websites or prove that work has been completed. Its recommendation is advisory.</p></div><h3>Your credentials stay on the backend.</h3><p>PayPal and Gemini credentials belong in your server configuration. The operator token is entered only when a protected action needs it.</p></section><section className="panel settings-panel settings-wide"><h2>A clearer hackathon demo</h2><p>Show a complete delivery, then try missing evidence. Explain why the agent pauses, make the human decision, and follow the actual Sandbox payout to a confirmed status.</p><button className="secondary-button" type="button" onClick={() => setDemoOpen(true)}><Icon name="play" size={15} />Open the sample walkthrough</button></section></div>}
        <footer className="workspace-footer"><span><Icon name="shield" size={13} />Designed for trust. Built for what’s next.</span><span>PalPay AI<span className="footer-dot">·</span>Hackathon build<span className="footer-dot">·</span>Sandbox funds only</span></footer>
      </main>
    </div>
    {demoOpen && <GuidedDemo onClose={() => setDemoOpen(false)} onStart={startAgreement} />}
  </div>;
}

export default App;
