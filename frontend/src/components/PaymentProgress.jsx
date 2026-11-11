
import "./PaymentProgress.css";

const STEPS = [
  "Rule Created",
  "Evidence Submitted",
  "AI Recommends",
  "Payment Authorized",
  "Payout Submitted",
  "Payment Confirmed",
];

const STATUS_STAGE = {
  WAITING_FOR_CONDITION: 1,
  CONDITION_SUBMITTED: 2,
  NEEDS_REVIEW: 2,
  AI_REJECTED: 2,
  EVIDENCE_REQUESTED: 1,
  HUMAN_REJECTED: 2,
  AWAITING_USER_APPROVAL: 3,
  USER_APPROVED: 4,
  PAYOUT_REQUESTED: 4,
  PAYOUT_UNKNOWN: 4,
  PAYOUT_DENIED: 4,
  PAYOUT_CANCELED: 4,
  PAYOUT_FAILED: 4,
  PAYOUT_SUBMITTED: 5,
  PAYOUT_UNCLAIMED: 5,
  PAYOUT_ON_HOLD: 5,
  PAYOUT_RETURNED: 5,
  PAYOUT_REFUNDED: 5,
  PAYOUT_REVERSED: 5,
  PAID: 6,
};

const STATUS_MESSAGES = {
  WAITING_FOR_CONDITION:
    "Waiting for the recipient to submit evidence.",

  CONDITION_SUBMITTED:
    "Evidence submitted. Gemini AI review is required.",

  NEEDS_REVIEW:
    "The evidence needs human attention before progressing.",

  AI_REJECTED:
    "Gemini rejected the evidence. Improved evidence may be submitted.",

  EVIDENCE_REQUESTED:
    "A human reviewer requested additional evidence.",

  HUMAN_REJECTED:
    "The human reviewer rejected the evidence. This review cycle is closed.",

  AWAITING_USER_APPROVAL:
    "AI recommended approval. Authorized payment approval is required.",

  USER_APPROVED:
    "Payment approved. A Sandbox payout has not been submitted yet.",

  PAYOUT_REQUESTED:
    "The Sandbox payout request is being processed.",

  PAYOUT_SUBMITTED:
    "Payout submitted. Waiting for confirmation from PayPal.",

  PAYOUT_UNKNOWN:
    "Payout outcome is uncertain. Reconciliation is required.",

  PAYOUT_FAILED:
    "The payout failed. No new payout should be initiated automatically.",

  PAYOUT_DENIED:
    "PayPal denied the payout.",

  PAYOUT_RETURNED:
    "The payout was returned.",

  PAYOUT_REFUNDED:
    "The payout was refunded.",

  PAYOUT_REVERSED:
    "The payout was reversed.",

  PAID:
    "PayPal confirmed the payment successfully.",
};

const ALERT_STATUSES = new Set([
  "HUMAN_REJECTED",
  "AI_REJECTED",
  "PAYOUT_UNKNOWN",
  "PAYOUT_FAILED",
  "PAYOUT_DENIED",
  "PAYOUT_RETURNED",
  "PAYOUT_REFUNDED",
  "PAYOUT_REVERSED",
]);

export default function PaymentProgress({ status }) {
  const currentStage = STATUS_STAGE[status] ?? 0;
  const isPaid = status === "PAID";
  const hasAlert = ALERT_STATUSES.has(status);

  return (
    <section className="payment-card payment-progress">
      <h2>Payment Progress</h2>

      <p className="payment-progress-description">
        Follow the current stage of your SmartPay payment.
      </p>

      <ol className="payment-progress-steps">
        {STEPS.map((step, index) => {
          const complete = isPaid || index < currentStage;
          const current =
            !isPaid && index === currentStage;

          const state = complete
            ? "complete"
            : current
              ? hasAlert
                ? "alert"
                : "current"
              : "upcoming";

          return (
            <li
              key={step}
              className={`payment-progress-step ${state}`}
              aria-current={current ? "step" : undefined}
            >
              <span className="payment-progress-number">
                {complete ? "✓" : index + 1}
              </span>

              <span className="payment-progress-label">
                {step}
              </span>
            </li>
          );
        })}
      </ol>

      <p
        className={`payment-progress-message ${
          hasAlert ? "warning" : ""
        }`}
        role="status"
      >
        {STATUS_MESSAGES[status] ??
          `Current payment status: ${status.replaceAll("_", " ")}`}
      </p>
    </section>
  );
}
