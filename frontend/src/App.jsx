
import { useState } from "react";
import "./App.css";

import CreateSmartPayForm from "./components/CreateSmartPayForm";
import EvidenceSubmissionForm from "./components/EvidenceSubmissionForm";
import AIReview from "./components/AIReview";
import HumanApproval from "./components/HumanApproval";
import PaymentTracking from "./components/PaymentTracking";
import SandboxPayout from "./components/SandboxPayout";
import PaymentHistory from "./components/PaymentHistory";
import DashboardAnalytics from "./components/DashboardAnalytics";
import ReviewQueue from "./components/ReviewQueue";

const PAGES = {
  dashboard: {
    label: "Dashboard",
    description: "Manage your intelligent conditional payments.",
  },
  payments: {
    label: "Payments",
    description: "View your PayPal Sandbox payment history.",
  },
  reviews: {
    label: "AI Reviews",
    description: "Review evidence using Gemini AI.",
  },
  settings: {
    label: "Settings",
    description: "PalPay AI Sandbox information.",
  },
};

const REVIEW_STATUSES = [
  "CONDITION_SUBMITTED",
  "AWAITING_USER_APPROVAL",
  "AI_REJECTED",
  "NEEDS_REVIEW",
];

const TRACKING_STATUSES = [
  "USER_APPROVED",
  "PAYOUT_REQUESTED",
  "PAYOUT_SUBMITTED",
  "PAYOUT_UNKNOWN",
  "PAYOUT_DENIED",
  "PAID",
  "PAYOUT_FAILED",
  "PAYOUT_RETURNED",
  "PAYOUT_REFUNDED",
];

function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [ruleId, setRuleId] = useState("3");
  const [rule, setRule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const showRuleLookup =
    activePage === "dashboard" || activePage === "reviews";

  async function refreshRule(id) {
    const response = await fetch(`/api/rules/smartpay/${id}`);

    if (!response.ok) {
      throw new Error("Unable to refresh payment status");
    }

    const updatedRule = await response.json();
    setRule(updatedRule);
  }

  async function fetchSmartPay(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setRule(null);

    try {
      await refreshRule(ruleId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function openReviewFromQueue(selectedRuleId) {
    setRuleId(String(selectedRuleId));
    setRule(null);
    setError("");
    setLoading(true);

    try {
      await refreshRule(selectedRuleId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
}

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <h2>PalPay AI</h2>
        <p>Smart Payments</p>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {Object.entries(PAGES).map(([page, config]) => (
            <button
              key={page}
              type="button"
              className={activePage === page ? "active" : ""}
              aria-current={
                activePage === page ? "page" : undefined
              }
              onClick={() => setActivePage(page)}
            >
              {config.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        {/* Page heading */}
        <header className="dashboard-header">
          <div>
            <h1>{PAGES[activePage].label}</h1>
            <p>{PAGES[activePage].description}</p>
          </div>
        </header>

        {activePage === "reviews" && (
        <ReviewQueue
          onSelectRule={openReviewFromQueue}
        />
        )}

        {/* Dashboard: Payment Analytics */}
        {activePage === "dashboard" && (
          <DashboardAnalytics />
        )}

        {/* Dashboard: Create SmartPay */}
        {activePage === "dashboard" && (
          <CreateSmartPayForm
            onCreated={(newRule) => {
              setRuleId(String(newRule.id));
              setRule(newRule);
              setError("");
            }}
          />
        )}

        {/* Rule search: Available on Dashboard and AI Reviews */}
        {showRuleLookup && (
          <>
            <section className="search-section">
              <h2>Find SmartPay Payment</h2>

              <form onSubmit={fetchSmartPay}>
                <input
                  type="number"
                  min="1"
                  required
                  value={ruleId}
                  onChange={(event) =>
                    setRuleId(event.target.value)
                  }
                  placeholder="Enter Rule ID"
                  aria-label="SmartPay Rule ID"
                />

                <button type="submit" disabled={loading}>
                  {loading ? "Loading..." : "Find Payment"}
                </button>
              </form>

              {error && <p role="alert">{error}</p>}
            </section>

            {rule && (
              <section className="payment-card">
                <h2>Payment #{rule.id}</h2>

                <div className="payment-amount">
                  {new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: rule.currency,
                  }).format(rule.amount)}
                </div>

                <p>
                  <strong>Recipient:</strong> {rule.recipient_name}
                </p>

                <p>
                  <strong>Status: </strong>
                  <span
                    className={`status-badge ${
                      rule.status === "PAID" ? "paid" : "pending"
                    }`}
                  >
                    {rule.status.replaceAll("_", " ")}
                  </span>
                </p>

                <p>
                  <strong>Description:</strong> {rule.description}
                </p>

                <p>
                  <strong>Condition:</strong> {rule.condition}
                </p>
              </section>
            )}
          </>
        )}

        {/* Dashboard: Evidence submission */}
        {activePage === "dashboard" &&
          rule?.status === "WAITING_FOR_CONDITION" && (
            <EvidenceSubmissionForm
              key={rule.id}
              ruleId={rule.id}
              onSubmitted={async () => {
                try {
                  await refreshRule(rule.id);
                } catch {
                  setError(
                    "Evidence was submitted, but the payment could not " +
                    "be refreshed. Use Find Payment to reload it."
                  );
                }
              }}
            />
          )}

        {/* AI Review: Available on Dashboard and AI Reviews */}
        {showRuleLookup &&
          rule?.status === "CONDITION_SUBMITTED" && (
            <AIReview
              key={rule.id}
              rule={rule}
              onReviewed={() => refreshRule(rule.id)}
            />
        )}

        {activePage === "reviews" &&
        rule &&
        ["NEEDS_REVIEW", "AI_REJECTED"].includes(rule.status) && (
          <section className="payment-card">
            <h2>
              {rule.status === "NEEDS_REVIEW"
                ? "Human Attention Required"
                : "Evidence Rejected"}
            </h2>
              
            <p>
              Rule #{rule.id} cannot currently undergo another
              AI review.
            </p>
              
            <p>
              A new evidence submission or an authorized human
              review workflow is required before proceeding.
            </p>
              
            <p>
              No payment will be initiated from this review state.
            </p>
          </section>
        )}
        
        {/* Dashboard: Human approval */}
        {activePage === "dashboard" &&
          rule &&
          ["AWAITING_USER_APPROVAL", "USER_APPROVED"].includes(
            rule.status
          ) && (
            <HumanApproval
              key={rule.id}
              rule={rule}
              onApproved={() => refreshRule(rule.id)}
            />
          )}

        {/* Dashboard: Payment tracking */}
        {activePage === "dashboard" &&
          rule &&
          TRACKING_STATUSES.includes(rule.status) && (
            <PaymentTracking
              key={rule.id}
              rule={rule}
              onRefresh={() => refreshRule(rule.id)}
            />
          )}

        {/* Dashboard: Sandbox payout */}
        {activePage === "dashboard" &&
          rule?.status === "USER_APPROVED" && (
            <SandboxPayout
              key={rule.id}
              rule={rule}
              onPayoutSubmitted={() => refreshRule(rule.id)}
            />
          )}

        {/* Payments page */}
        {activePage === "payments" && <PaymentHistory />}

        {/* AI Reviews: Informational states */}
        {activePage === "reviews" && !rule && (
          <section className="payment-card">
            <h2>Select a payment to review</h2>
            <p>
              Enter a SmartPay rule ID above and click Find Payment.
            </p>
          </section>
        )}

        {activePage === "reviews" &&
          rule &&
          !REVIEW_STATUSES.includes(rule.status) && (
            <section className="payment-card">
              <h2>AI Review Unavailable</h2>
              <p>
                Rule #{rule.id} currently has status{" "}
                <strong>{rule.status.replaceAll("_", " ")}</strong>.
              </p>
              <p>
                An AI review can be requested after the payment
                condition has been submitted. Use Dashboard for
                evidence submission and payment approval.
              </p>
            </section>
          )}

        {/* Settings: Informational page */}
        {activePage === "settings" && (
          <section className="payment-card">
            <h2>Sandbox Configuration</h2>
            <p>
              PalPay AI is currently configured for PayPal
              Sandbox development and testing.
            </p>

            <h3>Payment Security</h3>
            <p>
              The current demo uses an operator approval token.
              Production deployment will require user login,
              permission checks, and payment ownership validation.
            </p>

            <h3>Developer Settings</h3>
            <p>
              PayPal API credentials, webhook identifiers,
              and other secrets are configured on the backend,
              not in this frontend.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
