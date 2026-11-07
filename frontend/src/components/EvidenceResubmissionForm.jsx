
import { useState } from "react";
import "./EvidenceResubmissionForm.css";

export default function EvidenceResubmissionForm({
  rule,
  onSubmitted,
}) {
  const [description, setDescription] = useState("");
  const [fileUrl, setFileUrl] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    if (loading || submitted) return;

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/resubmit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-approval-token": token,
          },
          body: JSON.stringify({
            description: description.trim(),
            file_url: fileUrl.trim(),
          }),
        }
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Resubmission failed (HTTP ${response.status})`
        );
      }

      setSubmitted(true);

      setSuccess(
        "Improved evidence submitted successfully. " +
        "The rule is ready for another AI review."
      );

      setDescription("");
      setFileUrl("");

      try {
        await onSubmitted();
      } catch {
        setError(
          "Evidence was saved, but the rule could not " +
          "be refreshed. Use Find Payment to reload it."
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  return (
    <section className="resubmit-evidence">
      <h2>Submit Improved Evidence</h2>

      <p>
        Rule #{rule.id} requires additional evidence
        before another AI review can begin.
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="improved-evidence-description">
          Improved Evidence Description
        </label>

        <textarea
          id="improved-evidence-description"
          value={description}
          onChange={(event) =>
            setDescription(event.target.value)
          }
          placeholder="Explain what you improved or completed..."
          rows={5}
          required
          disabled={loading || submitted}
        />

        <label htmlFor="improved-evidence-url">
          Evidence URL (optional)
        </label>

        <input
          id="improved-evidence-url"
          type="url"
          value={fileUrl}
          onChange={(event) =>
            setFileUrl(event.target.value)
          }
          placeholder="https://example.com/evidence"
          disabled={loading || submitted}
        />

        <label htmlFor="resubmission-token">
          Demo Approval Token
        </label>

        <input
          id="resubmission-token"
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
            !description.trim() ||
            !token
          }
        >
          {loading
            ? "Submitting..."
            : submitted
              ? "Evidence Submitted"
              : "Submit Improved Evidence"}
        </button>
      </form>

      {error && (
        <p className="resubmit-error" role="alert">
          {error}
        </p>
      )}

      {success && (
        <p className="resubmit-success" role="status">
          {success}
        </p>
      )}
    </section>
  );
}
