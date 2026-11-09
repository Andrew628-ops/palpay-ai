
import { useState } from "react";
import "./App.css";

import CreateSmartPayForm from "./components/CreateSmartPayForm";
import EvidenceSubmissionForm from "./components/EvidenceSubmissionForm";
import EvidenceResubmissionForm from "./components/EvidenceResubmissionForm";
import AIReview from "./components/AIReview";
import HumanApproval from "./components/HumanApproval";
import PaymentTracking from "./components/PaymentTracking";
import SandboxPayout from "./components/SandboxPayout";
import PaymentHistory from "./components/PaymentHistory";
import DashboardAnalytics from "./components/DashboardAnalytics";
import ReviewQueue from "./components/ReviewQueue";
import SubmissionHistory from "./components/SubmissionHistory";
import HumanReviewDecision from "./components/HumanReviewDecision";
import HumanDecisionHistory from "./components/HumanDecisionHistory";
import PaymentProgress from "./components/PaymentProgress";

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
  "NEEDS_REVIEW",
  "AI_REJECTED",
  "AWAITING_USER_APPROVAL",
  "EVIDENCE_REQUESTED",
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

  // Refresh the currently selected SmartPay rule.
  async function refreshRule(id) {
    const response = await fetch(
      `/api/rules/smartpay/${id}`
    );

    if (!response.ok) {
      throw new Error(
        `Unable to refresh payment (HTTP ${response.status})`
      );
    }

    const updatedRule = await response.json();

    setRule(updatedRule);

    return updatedRule;
  }

  // Search for a SmartPay rule using its ID.
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

  // Open a rule selected from the AI Review Queue.
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
      {/* SIDEBAR */}
      <aside className="sidebar">
        <h2>PalPay AI</h2>
        <p>Smart Payments</p>

        <nav
          className="sidebar-nav"
          aria-label="Main navigation"
        >
          {Object.entries(PAGES).map(([page, config]) => (
            <button
              key={page}
              type="button"
              className={
                activePage === page ? "active" : ""
              }
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

      {/* MAIN CONTENT */}
      <main className="main-content">

        {/* PAGE HEADER */}
        <header className="dashboard-header">
          <div>
            <h1>{PAGES[activePage].label}</h1>
            <p>{PAGES[activePage].description}</p>
          </div>
        </header>

        {/* DASHBOARD ANALYTICS */}
        {activePage === "dashboard" && (
          <DashboardAnalytics />
        )}

        {/* CREATE SMARTPAY RULE */}
        {activePage === "dashboard" && (
          <CreateSmartPayForm
            onCreated={(newRule) => {
              setRuleId(String(newRule.id));
              setRule(newRule);
              setError("");
            }}
          />
        )}

        {/* AI REVIEW QUEUE */}
        {activePage === "reviews" && (
          <ReviewQueue
            onSelectRule={openReviewFromQueue}
          />
        )}

        {/* SMARTPAY RULE SEARCH */}
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

                <button
                  type="submit"
                  disabled={loading}
                >
                  {loading
                    ? "Loading..."
                    : "Find Payment"}
                </button>
              </form>

              {error && (
                <p role="alert">{error}</p>
              )}
            </section>

            {/* SELECTED PAYMENT DETAILS */}
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
                  <strong>Recipient: </strong>
                  {rule.recipient_name}
                </p>

                <p>
                  <strong>Status: </strong>

                  <span
                    className={`status-badge ${
                      rule.status === "PAID"
                        ? "paid"
                        : "pending"
                    }`}
                  >
                    {rule.status.replaceAll("_", " ")}
                  </span>
                </p>

                <p>
                  <strong>Description: </strong>
                  {rule.description}
                </p>

                <p>
                  <strong>Condition: </strong>
                  {rule.condition}
                </p>
              </section>
            )}
          </>
        )}

        {/* INITIAL EVIDENCE SUBMISSION */}
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
                    "Evidence was submitted, but the " +
                    "payment could not be refreshed. " +
                    "Use Find Payment to reload it."
                  );
                }
              }}
            />
          )}

          {/* PAYMENT PROGRESS TIMELINE */}
          {rule && (
            <PaymentProgress
              key={rule.id}
              status={rule.status}
            />
          )}
          
        {/* GEMINI AI REVIEW */}
        {showRuleLookup &&
          rule?.status === "CONDITION_SUBMITTED" && (
            <AIReview
              key={rule.id}
              rule={rule}
              onReviewed={() =>
                refreshRule(rule.id)
              }
            />
          )}

        {/* SUBMISSION HISTORY */}
        {activePage === "reviews" && rule && (
          <SubmissionHistory
            key={`${rule.id}-${rule.status}`}
            ruleId={rule.id}
          />
        )}

        {/* HUMAN EVIDENCE REVIEW */}
        {activePage === "reviews" &&
          rule?.status === "NEEDS_REVIEW" && (
            <HumanReviewDecision
              key={rule.id}
              rule={rule}
              onDecided={() => refreshRule(rule.id)}
            />
          )}

        {/* IMPROVED EVIDENCE RESUBMISSION */}
        {activePage === "reviews" &&
          rule &&
          [
            "AI_REJECTED",
            "EVIDENCE_REQUESTED",
          ].includes(rule.status) && (
            <EvidenceResubmissionForm
              key={rule.id}
              rule={rule}
              onSubmitted={() =>
                refreshRule(rule.id)
              }
            />
          )}

        
        {/* HUMAN DECISION HISTORY */}
        {activePage === "reviews" && rule && (
          <HumanDecisionHistory
            key={`${rule.id}-${rule.status}`}
            ruleId={rule.id}
          />
        )}

        {/* HUMAN APPROVAL INFORMATION */}
        {activePage === "reviews" &&
          rule?.status === "AWAITING_USER_APPROVAL" && (
            <section className="payment-card">
              <h2>Awaiting Human Approval</h2>

              <p>
                Gemini has completed the AI review
                for Rule #{rule.id}.
              </p>

              <p>
                Open this rule on the Dashboard to
                complete the authorized human
                approval process.
              </p>

              <p>
                No payment has been sent by this step.
              </p>
            </section>
          )}

        {/* HUMAN APPROVAL */}
        {activePage === "dashboard" &&
          rule &&
          [
            "AWAITING_USER_APPROVAL",
            "USER_APPROVED",
          ].includes(rule.status) && (
            <HumanApproval
              key={rule.id}
              rule={rule}
              onApproved={() =>
                refreshRule(rule.id)
              }
            />
          )}

        {/* PAYMENT TRACKING */}
        {activePage === "dashboard" &&
          rule &&
          TRACKING_STATUSES.includes(
            rule.status
          ) && (
            <PaymentTracking
              key={rule.id}
              rule={rule}
              onRefresh={() =>
                refreshRule(rule.id)
              }
            />
          )}

        {/* PAYPAL SANDBOX PAYOUT */}
        {activePage === "dashboard" &&
          rule?.status === "USER_APPROVED" && (
            <SandboxPayout
              key={rule.id}
              rule={rule}
              onPayoutSubmitted={() =>
                refreshRule(rule.id)
              }
            />
          )}

        {/* PAYMENTS HISTORY PAGE */}
        {activePage === "payments" && (
          <PaymentHistory />
        )}

        {/* AI REVIEWS: NO RULE SELECTED */}
        {activePage === "reviews" && !rule && (
          <section className="payment-card">
            <h2>Select a Payment to Review</h2>

            <p>
              Load the AI Review Queue and select
              a SmartPay rule, or enter a rule ID
              in the search field above.
            </p>
          </section>
        )}

        {/* AI REVIEWS: NOT ELIGIBLE */}
        {activePage === "reviews" &&
          rule &&
          !REVIEW_STATUSES.includes(
            rule.status
          ) && (
            <section className="payment-card">
              <h2>AI Review Unavailable</h2>

              <p>
                Rule #{rule.id} currently has status{" "}
                <strong>
                  {rule.status.replaceAll("_", " ")}
                </strong>.
              </p>

              <p>
                The rule is not currently eligible
                for another AI review.
              </p>

              <p>
                Submission History remains available
                for viewing previous evidence.
              </p>
            </section>
          )}

        {/* SETTINGS PAGE */}
        {activePage === "settings" && (
          <section className="payment-card">
            <h2>Sandbox Configuration</h2>

            <p>
              PalPay AI is currently configured
              for PayPal Sandbox development
              and testing.
            </p>

            <h3>Payment Security</h3>

            <p>
              This demo uses an operator approval token.
              Production deployment will require
              proper user authentication, permission
              checks, and payment ownership validation.
            </p>

            <h3>Developer Settings</h3>

            <p>
              PayPal API credentials, webhook
              identifiers, and other secrets
              are configured on the backend,
              not in this frontend.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
