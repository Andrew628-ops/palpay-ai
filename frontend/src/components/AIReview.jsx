
import { useState } from "react";

function AIReview({ rule, onReviewed }) {
  const [token, setToken] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canReview = rule.status === "CONDITION_SUBMITTED";

  async function handleReview(event) {
    event.preventDefault();

    if (!canReview || loading || !token.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/ai-review`,
        {
          method: "POST",
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
            : `AI review failed (HTTP ${response.status})`
        );
      }

      setResult(data);

      // Refresh the dashboard after a successful review.
      try {
        await onReviewed?.();
      } catch {
        setError(
          "AI review completed, but the dashboard " +
          "could not refresh. Reload the page."
        );
      }

    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      // Do not retain the token after the request.
      setToken("");
      setLoading(false);
    }
  }

  const confidence = Number(result?.confidence);

  const confidencePercentage =
    Number.isFinite(confidence) &&
    confidence >= 0 &&
    confidence <= 100
      ? confidence <= 1
        ? confidence * 100
        : confidence
      : null;

  return (
    <section className="ai-review-section">
      <h2>Gemini AI Review</h2>

      <p>
        Let Gemini analyze the submitted evidence
        against the payment condition.
      </p>

      {canReview && (
        <form onSubmit={handleReview}>
          <label htmlFor={`ai-review-token-${rule.id}`}>
            Demo Operator Token
          </label>

          <input
            id={`ai-review-token-${rule.id}`}
            type="password"
            value={token}
            onChange={(event) =>
              setToken(event.target.value)
            }
            placeholder="Enter your demo approval token"
            autoComplete="off"
            required
            disabled={loading}
          />

          <button
            type="submit"
            disabled={loading || !token.trim()}
          >
            {loading
              ? "Analyzing Evidence..."
              : "Run AI Review"}
          </button>
        </form>
      )}

      {loading && (
        <p role="status">
          Gemini is analyzing the submitted evidence...
        </p>
      )}

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {result && !canReview && (
        <div className="ai-result">
          <h3>AI Review Result</h3>

          <p>
            <strong>Recommendation: </strong>
            <span>{result.recommendation}</span>
          </p>

          {confidencePercentage !== null && (
            <p>
              <strong>Confidence: </strong>
              {confidencePercentage.toFixed(0)}%
            </p>
          )}

          <p>
            <strong>AI Analysis:</strong>
          </p>

          <p>{result.analysis}</p>

          <p className="ai-advisory">
            This recommendation assesses the submitted description.
            It is not independent verification of the work or permission to pay.
          </p>
        </div>
      )}

      {!canReview && !result && (
        <p>
          Current payment status:{" "}
          {rule.status.replaceAll("_", " ")}
        </p>
      )}
    </section>
  );
}

export default AIReview;
