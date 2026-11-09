
import { useState } from "react";
import "./HumanReview.css";

export default function HumanReviewDecision({
  rule,
  onDecided,
}) {
  const [decision, setDecision] = useState(
    "REQUEST_MORE_EVIDENCE"
  );
  const [reason, setReason] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const canReview = rule.status === "NEEDS_REVIEW";

  async function handleSubmit(event) {
    event.preventDefault();

    if (
      !canReview ||
      loading ||
      submitted ||
      reason.trim().length < 10 ||
      !token.trim()
    ) {
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `/api/reviews/${rule.id}/human-decision`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-approval-token": token.trim(),
          },
          body: JSON.stringify({
            decision,
            reason: reason.trim(),
          }),
        }
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Human review failed (HTTP ${response.status})`
        );
      }

      setSubmitted(true);
      setSuccess(
        "Human review decision recorded successfully."
      );

      // Refresh the rule so App.jsx displays
      // the correct next workflow component.
      try {
        await onDecided?.();
      } catch {
        setError(
          "Decision was saved, but the rule could " +
          "not be refreshed. Reload the rule."
        );
      }
    } catch (err) {
      setError(err.message || "Unable to save decision");
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  if (!canReview) {
    return null;
  }

  return (
    <section className="payment-card human-review-card">
      <h2>Human Evidence Review</h2>

      <p>
        Gemini could not fully verify the submitted
        evidence for Rule #{rule.id}.
      </p>

      <p>
        Examine the evidence in Submission History
        before recording your decision.
      </p>

      <form
        onSubmit={handleSubmit}
        className="human-review-form"
      >
        <label htmlFor="human-review-decision">
          Review Decision
        </label>

        <select
          id="human-review-decision"
          value={decision}
          onChange={(event) =>
            setDecision(event.target.value)
          }
          disabled={loading || submitted}
        >
          <option value="REQUEST_MORE_EVIDENCE">
            Request More Evidence
          </option>

          <option value="REJECT">
            Reject Evidence
          </option>
        </select>

        <label htmlFor="human-review-reason">
          Reason for Decision
        </label>

        <textarea
          id="human-review-reason"
          value={reason}
          onChange={(event) =>
            setReason(event.target.value)
          }
          placeholder="Explain your review decision..."
          minLength={10}
          maxLength={2000}
          rows={5}
          required
          disabled={loading || submitted}
        />

        {decision === "REJECT" && (
          <p className="human-review-warning">
            Rejecting this evidence closes the current
            review cycle. The normal resubmission
            workflow will no longer be available.
          </p>
        )}

        <label htmlFor="human-review-token">
          Demo Operator Token
        </label>

        <input
          id="human-review-token"
          type="password"
          value={token}
          onChange={(event) =>
            setToken(event.target.value)
          }
          placeholder="Enter demo approval token"
          autoComplete="off"
          required
          disabled={loading || submitted}
        />

        <button
          type="submit"
          disabled={
            loading ||
            submitted ||
            reason.trim().length < 10 ||
            !token.trim()
          }
        >
          {loading
            ? "Saving Decision..."
            : submitted
              ? "Decision Recorded"
              : "Record Human Decision"}
        </button>
      </form>

      {error && (
        <p className="human-review-error" role="alert">
          {error}
        </p>
      )}

      {success && (
        <p className="human-review-success" role="status">
          {success}
        </p>
      )}
    </section>
  );
}
