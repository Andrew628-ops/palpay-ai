
import { useState } from "react";
import "./SubmissionHistory.css";

export default function SubmissionHistory({ ruleId }) {
  const [token, setToken] = useState("");
  const [submissions, setSubmissions] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setLoaded(false);
    setSubmissions([]);

    try {
      const response = await fetch(
        `/api/rules/smartpay/${ruleId}/submissions?limit=100`,
        {
          headers: {
            "x-approval-token": token,
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

      if (!Array.isArray(data.submissions)) {
        throw new Error("Invalid submission history response");
      }

      setSubmissions(data.submissions);
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  function safeEvidenceUrl(value) {
    if (!value) return null;

    try {
      const url = new URL(value);

      if (["http:", "https:"].includes(url.protocol)) {
        return url.href;
      }
    } catch {
      return null;
    }

    return null;
  }

  return (
    <section className="submission-history">
      <h2>Submission History</h2>

      <p>
        View previous evidence and AI review decisions
        for SmartPay Rule #{ruleId}.
      </p>

      <form
        onSubmit={loadHistory}
        className="submission-history-form"
      >
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Enter demo approval token"
          aria-label="Demo approval token for submission history"
          autoComplete="off"
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? "Loading..." : "Load History"}
        </button>
      </form>

      {error && (
        <p className="submission-history-error" role="alert">
          {error}
        </p>
      )}

      {loaded && (
        <div className="submission-history-results">
          <h3>Submissions ({submissions.length})</h3>

          {submissions.length === 0 && (
            <p>No evidence submissions found.</p>
          )}

          {submissions.map((submission) => {
            const evidenceUrl = safeEvidenceUrl(
              submission.file_url
            );

            return (
              <article
                key={submission.submission_id}
                className="submission-history-card"
              >
                <div className="submission-history-heading">
                  <h4>
                    Submission #{submission.submission_id}
                  </h4>

                  <span className="submission-history-status">
                    {submission.ai_recommendation
                      ? submission.ai_recommendation.replaceAll(
                          "_",
                          " "
                        )
                      : "NOT REVIEWED"}
                  </span>
                </div>

                <p>
                  <strong>Submitted:</strong>{" "}
                  {submission.submitted_at
                    ? submission.submitted_at
                        .replace("T", " ")
                        .split(".")[0]
                    : "Unknown"}
                </p>

                <div className="submission-history-detail">
                  <strong>Evidence Description</strong>
                  <p>{submission.description}</p>
                </div>

                <div className="submission-history-detail">
                  <strong>Evidence Link</strong>

                  {evidenceUrl ? (
                    <p>
                      <a
                        href={evidenceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View Submitted Evidence
                      </a>
                    </p>
                  ) : (
                    <p>No valid evidence link provided.</p>
                  )}
                </div>

                <div className="submission-history-analysis">
                  <strong>Gemini AI Analysis</strong>

                  <p>
                    {submission.ai_analysis ||
                      "This submission has not been reviewed yet."}
                  </p>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
