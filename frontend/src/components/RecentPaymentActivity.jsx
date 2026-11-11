
import { useState } from "react";
import "./RecentPaymentActivity.css";

function formatAmount(payment) {
  const amount = Number(payment.amount);

  if (!Number.isFinite(amount)) {
    return "Amount unavailable";
  }

  return `${payment.currency} ${amount.toFixed(2)}`;
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  return String(value)
    .replace("T", " ")
    .split(".")[0];
}

function getPaymentStatus(payment) {
  const status =
    payment.rule_status === "PAID" &&
    payment.payout_status === "PAYOUT_COMPLETED"
      ? "PAID"
      : payment.payout_status || "UNKNOWN";

  const isPaid = status === "PAID";

  const isProblem = [
    "PAYOUT_FAILED",
    "PAYOUT_DENIED",
    "PAYOUT_CANCELED",
    "PAYOUT_RETURNED",
    "PAYOUT_REFUNDED",
    "PAYOUT_REVERSED",
  ].includes(status);

  return {
    label: status.replaceAll("_", " "),
    tone: isPaid
      ? "success"
      : isProblem
        ? "danger"
        : "pending",
  };
}

export default function RecentPaymentActivity({
  onViewAll,
}) {
  const [token, setToken] = useState("");
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function loadActivity(event) {
    event.preventDefault();

    if (loading || !token.trim()) return;

    setLoading(true);
    setError("");
    setLoaded(false);
    setPayments([]);

    try {
      const response = await fetch(
        "/api/payments/history?limit=5",
        {
          headers: {
            "x-approval-token": token.trim(),
          },
          cache: "no-store",
        }
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Unable to load activity (HTTP ${response.status})`
        );
      }

      if (!Array.isArray(data?.payments)) {
        throw new Error(
          "Invalid payment activity response"
        );
      }

      setPayments(data.payments);
      setLoaded(true);
    } catch (err) {
      setError(
        err.message || "Unable to retrieve recent payments"
      );
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  return (
    <section className="recent-activity">
      <div className="recent-activity-heading">
        <div>
          <h2>Recent Payment Activity</h2>
          <p>
            Your latest PayPal Sandbox payout records.
          </p>
        </div>

        {loaded && onViewAll && (
          <button
            type="button"
            className="recent-view-all"
            onClick={onViewAll}
          >
            View All Payments
          </button>
        )}
      </div>

      <form
        onSubmit={loadActivity}
        className="recent-activity-form"
      >
        <input
          type="password"
          value={token}
          onChange={(event) =>
            setToken(event.target.value)
          }
          placeholder="Enter demo approval token"
          aria-label="Demo token for recent activity"
          autoComplete="off"
          required
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !token.trim()}
        >
          {loading ? "Loading..." : "Load Activity"}
        </button>
      </form>

      {error && (
        <p className="recent-activity-error" role="alert">
          {error}
        </p>
      )}

      {loaded && (
        <>
          <h3 className="recent-activity-count">
            Recent Payouts ({payments.length})
          </h3>

          {payments.length === 0 ? (
            <p className="recent-activity-empty">
              No Sandbox payout records found.
            </p>
          ) : (
            <div className="recent-activity-list">
              {payments.map((payment) => {
                const status = getPaymentStatus(payment);

                return (
                  <article
                    key={payment.rule_id}
                    className="recent-activity-item"
                  >
                    <div className="recent-activity-icon">
                      $
                    </div>

                    <div className="recent-activity-details">
                      <strong>
                        {payment.recipient_name}
                      </strong>

                      <span>
                        SmartPay Rule #{payment.rule_id}
                      </span>

                      <small>
                        {formatDate(payment.created_at)}
                      </small>
                    </div>

                    <div className="recent-activity-payment">
                      <strong>
                        {formatAmount(payment)}
                      </strong>

                      <span
                        className={
                          `recent-activity-status ${status.tone}`
                        }
                      >
                        {status.label}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}
