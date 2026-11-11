
import { useState } from "react";
import "./DashboardAnalytics.css";

export default function DashboardAnalytics() {
  const [token, setToken] = useState("");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);

  async function loadAnalytics(event) {
    event.preventDefault();

    if (loading || !token.trim()) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/payments/summary", {
        headers: {
          "x-approval-token": token.trim(),
        },
        cache: "no-store",
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Unable to load analytics (HTTP ${response.status})`
        );
      }

      const validCounts = [
        "total_rules",
        "completed_payouts",
        "awaiting_approval",
      ].every(
        (field) =>
          Number.isInteger(data?.[field]) &&
          data[field] >= 0
      );

      const volume = Number(data?.completed_volume_usd);

      if (
        !validCounts ||
        data.completed_volume_usd == null ||
        !Number.isFinite(volume) ||
        volume < 0
      ) {
        throw new Error("Invalid analytics response");
      }

      setStats(data);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err.message || "Unable to load analytics");
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  const completedVolume = stats
    ? new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(Number(stats.completed_volume_usd))
    : null;

  const completionPercent =
    stats && stats.total_rules > 0
      ? Math.min(
          100,
          Math.round(
            (stats.completed_payouts / stats.total_rules) * 100
          )
        )
      : 0;

  return (
    <section className="analytics-section">
      <div className="analytics-heading">
        <div>
          <h2>Payment Analytics</h2>
          <p>
            Monitor your SmartPay rules and confirmed
            PayPal Sandbox payouts.
          </p>
        </div>

        <span className="analytics-demo-badge">
          SANDBOX
        </span>
      </div>

      <form
        onSubmit={loadAnalytics}
        className="analytics-auth-form"
      >
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Enter demo approval token"
          aria-label="Demo approval token for analytics"
          autoComplete="off"
          required
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !token.trim()}
        >
          {loading ? "Loading Analytics..." : "Load Analytics"}
        </button>
      </form>

      {error && (
        <p className="analytics-error" role="alert">
          {error}
        </p>
      )}

      {stats && (
        <>
          <div className="analytics-grid">
            <article className="analytics-card analytics-card--rules">
              <span>Total SmartPay Rules</span>

              <h3>{stats.total_rules}</h3>

              <p>All created payment rules</p>
            </article>

            <article className="analytics-card analytics-card--paid">
              <span>Completed Payouts</span>

              <h3>{stats.completed_payouts}</h3>

              <p>Confirmed Sandbox transactions</p>
            </article>

            <article className="analytics-card analytics-card--approval">
              <span>Awaiting Approval</span>

              <h3>{stats.awaiting_approval}</h3>

              <p>Waiting for human authorization</p>
            </article>

            <article className="analytics-card analytics-card--volume">
              <span>Completed USD Volume</span>

              <h3>{completedVolume}</h3>

              <p>Total confirmed Sandbox payouts</p>
            </article>
          </div>

          <div className="analytics-progress-panel">
            <div className="analytics-progress-header">
              <div>
                <h3>Payment Completion Overview</h3>

                <p>
                  Percentage of all created rules
                  with confirmed payouts.
                </p>
              </div>

              <strong>{completionPercent}%</strong>
            </div>

            <div
              className="analytics-progress-track"
              role="progressbar"
              aria-label="Share of rules with confirmed payouts"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={completionPercent}
            >
              <div
                className="analytics-progress-fill"
                style={{ width: `${completionPercent}%` }}
              />
            </div>

            <p className="analytics-progress-caption">
              {stats.completed_payouts} of{" "}
              {stats.total_rules} rules have confirmed payouts.
            </p>
          </div>

          <div className="analytics-footer">
            <span>
              Environment: {stats.environment || "Unknown"}
            </span>

            {updatedAt && (
              <span>
                Last loaded:{" "}
                {updatedAt.toLocaleTimeString()}
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
