import { useMemo, useState } from "react";
import "./PaymentHistory.css";

export default function PaymentHistory() {
  const [token, setToken] = useState("");
  const [payments, setPayments] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function fetchPayments(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setLoaded(false);
    setPayments([]);

    try {
      const response = await fetch(
        "/api/payments/history?limit=100",
        {
          headers: {
            "x-approval-token": token,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Unable to load payments (HTTP ${response.status})`
        );
      }

      const data = await response.json();

      if (!Array.isArray(data.payments)) {
        throw new Error("Invalid payment history response");
      }

      setPayments(data.payments);
      setLoaded(true);
      setToken("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const filteredPayments = useMemo(() => {
    const keyword = search.toLowerCase().trim();

    return payments.filter((payment) => {
      return [
        payment.rule_id,
        payment.recipient_name,
        payment.amount,
        payment.currency,
        payment.rule_status,
        payment.payout_status,
      ]
        .some((value) =>
          String(value ?? "").toLowerCase().includes(keyword)
        );
    });
  }, [payments, search]);

  return (
    <section className="payment-history">
      <h2>Payment History</h2>

      <p>
        View and search your PayPal Sandbox payment records.
      </p>

      <form
        onSubmit={fetchPayments}
        className="history-auth-form"
      >
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Enter demo approval token"
          aria-label="Operator token for payment history"
          autoComplete="off"
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? "Loading..." : "Load Payments"}
        </button>
      </form>

      {error && <p className="history-error">{error}</p>}

      {loaded && (
        <>
          <div className="history-controls">
            <h3>
              Payments ({filteredPayments.length})
            </h3>

            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search payments..."
              aria-label="Search payment history"
            />
          </div>

          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Rule ID</th>
                  <th>Recipient</th>
                  <th>Amount</th>
                  <th>Payment Status</th>
                  <th>Date</th>
                </tr>
              </thead>

              <tbody>
                {filteredPayments.map((payment) => (
                  <tr key={payment.rule_id}>
                    <td>#{payment.rule_id}</td>
                    <td>{payment.recipient_name}</td>

                    <td>
                      {payment.currency}{" "}
                      {Number(payment.amount).toFixed(2)}
                    </td>

                    <td>
                      <span
                        className={
                          payment.rule_status === "PAID"
                            ? "history-status paid"
                            : "history-status pending"
                        }
                      >
                        {payment.rule_status}
                      </span>
                    </td>

                    <td>
                      {payment.created_at
                        ? payment.created_at
                            .replace("T", " ")
                            .split(".")[0]
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {filteredPayments.length === 0 && (
              <p>No matching payments found.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
