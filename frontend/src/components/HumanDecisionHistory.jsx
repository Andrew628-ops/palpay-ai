
import { useState } from "react";
import "./HumanReview.css";

export default function HumanDecisionHistory({ ruleId }) {
  const [token, setToken] = useState("");
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory(event) {
    event.preventDefault();

    if (loading || !token.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    setLoaded(false);
    setDecisions([]);

    try {
      const response = await fetch(
        `/api/reviews/${ruleId}/human-decisions?limit=100`,
        {
          headers: {
            "x-approval-token": token.trim(),
          },
        }
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Unable to load history (HTTP ${response.status})`
        );
      }

      if (!Array.isArray(data?.decisions)) {
        throw new Error(
          "Invalid human decision history response"
        );
      }

      setDecisions(data.decisions);
      setLoaded(true);
    } catch (err) {
      setError(err.message || "Unable to load history");
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  return (
    <section className="payment-card human-review-card">
      <h2>Human Decision History</h2>

      <p>
        View recorded human review decisions
        for SmartPay Rule #{ruleId}.
      </p>

      <form
        onSubmit={loadHistory}
        className="human-review-form"
      >
        <label htmlFor={`history-token-${ruleId}`}>
          Demo Operator Token
        </label>

        <input
          id={`history-token-${ruleId}`}
          type="password"
          value={token}
          onChange={(event) =>
            setToken(event.target.value)
          }
          placeholder="Enter demo approval token"
          autoComplete="off"
          required
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !token.trim()}
        >
          {loading ? "Loading..." : "Load Decision History"}
        </button>
      </form>

      {error && (
        <p className="human-review-error" role="alert">
          {error}
        </p>
      )}

      {loaded && (
        <div className="human-review-history">
          <h3>Decisions ({decisions.length})</h3>

          {decisions.length === 0 ? (
            <p>No human decisions recorded yet.</p>
          ) : (
            decisions.map((item) => (
              <article
                key={item.decision_id}
                className="human-review-history-item"
              >
                <h4>
                  Decision #{item.decision_id}
                </h4>

                <p>
                  <strong>Submission: </strong>
                  #{item.submission_id}
                </p>

                <p>
                  <strong>Decision: </strong>
                  {item.decision.replaceAll("_", " ")}
                </p>

                <p>
                  <strong>Reason: </strong>
                  {item.reason}
                </p>

                <p>
                  <strong>Reviewer: </strong>
                  {item.reviewer_id}
                </p>

                <p>
                  <strong>Recorded: </strong>
                  {item.created_at
                    ? item.created_at.replace("T", " ")
                    : "Not available"}
                </p>
              </article>
            ))
          )}
        </div>
      )}
    </section>
  );
}
