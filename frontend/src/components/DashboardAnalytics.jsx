
import { useState } from "react";
import "./DashboardAnalytics.css";

export default function DashboardAnalytics() {
  const [token, setToken] = useState("");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAnalytics(event) {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/payments/summary", {
        headers: {
          "x-approval-token": token,
        },
      });

      if (!response.ok) {
        throw new Error(
          `Unable to load analytics (HTTP ${response.status})`
        );
      }

      const data = await response.json();

      if (
        typeof data.total_rules !== "number" ||
        typeof data.completed_payouts !== "number" ||
        typeof data.awaiting_approval !== "number" ||
        data.completed_volume_usd == null
      ) {
        throw new Error("Invalid analytics response");
      }

      setStats(data);
      setToken("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const completedVolume = stats
    ? new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(Number(stats.completed_volume_usd))
    : null;

  return (
    <section className="analytics-section">
      <div className="analytics-heading">
        <div>
          <h2>Payment Analytics</h2>
          <p>Monitor your PayPal Sandbox payment activity.</p>
        </div>
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
        />

        <button type="submit" disabled={loading}>
          {loading ? "Loading..." : "Load Analytics"}
        </button>
      </form>

      {error && <p className="analytics-error" role="alert">{error}</p>}

      {stats && (
        <>
          <div className="analytics-grid">
            <div className="analytics-card">
              <span>Total SmartPay Rules</span>
              <h3>{stats.total_rules}</h3>
              <p>All created payment rules</p>
            </div>

            <div className="analytics-card">
              <span>Completed Payouts</span>
              <h3>{stats.completed_payouts}</h3>
              <p>Confirmed Sandbox transactions</p>
            </div>

            <div className="analytics-card">
              <span>Awaiting Approval</span>
              <h3>{stats.awaiting_approval}</h3>
              <p>Waiting for human authorization</p>
            </div>

            <div className="analytics-card">
              <span>Completed USD Volume</span>
              <h3>{completedVolume}</h3>
              <p>Total confirmed USD Sandbox payouts</p>
            </div>
          </div>

          <p className="analytics-environment">
            Environment: {stats.environment}
          </p>
        </>
      )}
    </section>
  );
}
