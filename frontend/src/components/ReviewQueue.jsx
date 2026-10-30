
import { useState } from "react";
import "./ReviewQueue.css";

export default function ReviewQueue({ onSelectRule }) {
  const [token, setToken] = useState("");
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function loadReviews(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setLoaded(false);
    setReviews([]);

    try {
      const response = await fetch(
        "/api/reviews/queue?limit=100",
        {
          headers: {
            "x-approval-token": token,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Unable to load AI reviews (HTTP ${response.status})`
        );
      }

      const data = await response.json();

      if (!Array.isArray(data.reviews)) {
        throw new Error("Invalid review queue response");
      }

      setReviews(data.reviews);
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  function formatStatus(status) {
    return status.replaceAll("_", " ");
  }

  return (
    <section className="review-queue">
      <h2>AI Review Queue</h2>
      <p>
        View SmartPay rules that need AI review or human approval.
      </p>

      <form onSubmit={loadReviews} className="review-queue-form">
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Enter demo approval token"
          autoComplete="off"
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? "Loading..." : "Load Reviews"}
        </button>
      </form>

      {error && <p className="review-queue-error" role="alert">
        {error}
      </p>}

      {loaded && (
        <>
          <h3>Reviews ({reviews.length})</h3>

          {reviews.length === 0 ? (
            <p>No rules currently require review.</p>
          ) : (
            <div className="review-queue-table-wrapper">
              <table className="review-queue-table">
                <thead>
                  <tr>
                    <th>Rule ID</th>
                    <th>Recipient</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {reviews.map((review) => (
                    <tr key={review.rule_id}>
                      <td>#{review.rule_id}</td>
                      <td>{review.recipient_name}</td>
                      <td>
                        {review.currency}{" "}
                        {Number(review.amount).toFixed(2)}
                      </td>
                      <td>
                        <span className="review-status">
                          {formatStatus(review.status)}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          onClick={() =>
                            onSelectRule(review.rule_id)
                          }
                        >
                          Open Review
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
