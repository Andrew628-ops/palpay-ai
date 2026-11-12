
import Icon from "./Icon";
import { money, statusLabel, statusTone } from "../lib/format";

import PaymentProgress from "./PaymentProgress";
import EvidenceSubmissionForm from "./EvidenceSubmissionForm";
import EvidenceResubmissionForm from "./EvidenceResubmissionForm";
import AIReview from "./AIReview";
import HumanApproval from "./HumanApproval";
import HumanReviewDecision from "./HumanReviewDecision";
import SandboxPayout from "./SandboxPayout";
import PaymentTracking from "./PaymentTracking";
import SubmissionHistory from "./SubmissionHistory";
import HumanDecisionHistory from "./HumanDecisionHistory";
import DemoPaymentSimulator from "./DemoPaymentSimulator";

export default function SelectedAgreement({
  rule,
  onRefresh,
  onClose,
  onError,
}) {
  const tracking = /^(USER_APPROVED|PAYOUT_|PAID)/.test(
    rule.status
  );

  // Show the simulated payment experience in production.
  // This is a UI choice, not a security boundary.
  const isHostedDemo = import.meta.env.PROD;

  async function updated() {
    try {
      await onRefresh(rule.id);
    } catch (error) {
      onError(
        `The action completed, but the agreement could not refresh. ${error.message}`
      );
    }
  }

  return (
    <section
      className="selected-agreement"
      id="selected-agreement"
      aria-label={`Agreement ${rule.id} details`}
    >
      {/* Agreement Header */}
      <div className="selected-agreement-header">
        <div>
          <span className="eyebrow">
            AGREEMENT #{String(rule.id).padStart(3, "0")}
          </span>

          <h2>{rule.description}</h2>

          <p>
            Payable to <strong>{rule.recipient_name}</strong>
          </p>
        </div>

        <div className="selected-amount">
          <strong>
            {money(rule.amount, rule.currency)}
          </strong>

          <span
            className={`status-badge ${statusTone(rule.status)}`}
          >
            <i />
            {statusLabel(rule.status)}
          </span>
        </div>

        <button
          type="button"
          className="icon-button"
          aria-label="Close agreement details"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>

      {/* Agreement Condition */}
      <div className="agreement-condition">
        <Icon name="shield" size={19} />

        <div>
          <span>AGREED RELEASE CONDITION</span>
          <p>{rule.condition}</p>
        </div>
      </div>

      {/* Real Payment Progress */}
      <PaymentProgress status={rule.status} />

      {/* Agreement Workflow */}
      <div className="selected-workflow">

        {/* STEP 1: Submit Evidence */}
        {rule.status === "WAITING_FOR_CONDITION" && (
          <EvidenceSubmissionForm
            key={rule.id}
            ruleId={rule.id}
            onSubmitted={updated}
          />
        )}

        {/* STEP 2: Gemini AI Review */}
        {rule.status !== "WAITING_FOR_CONDITION" && (
          <AIReview
            key={rule.id}
            rule={rule}
            onReviewed={updated}
          />
        )}

        {/* STEP 3: Human Review for Uncertain AI Results */}
        {!isHostedDemo &&
          rule.status === "NEEDS_REVIEW" && (
            <HumanReviewDecision
              key={rule.id}
              rule={rule}
              onDecided={updated}
            />
          )}

        {/* Evidence Resubmission */}
        {["AI_REJECTED", "EVIDENCE_REQUESTED"].includes(
          rule.status
        ) && (
          <EvidenceResubmissionForm
            key={rule.id}
            rule={rule}
            onSubmitted={updated}
          />
        )}

        {/* STEP 4-6: Simulated Payment for Judges */}
        {isHostedDemo &&
          rule.status === "AWAITING_USER_APPROVAL" && (
            <DemoPaymentSimulator
              key={rule.id}
              rule={rule}
            />
          )}

        {/* Real Human Approval - Local Development */}
        {!isHostedDemo &&
          [
            "AWAITING_USER_APPROVAL",
            "USER_APPROVED",
          ].includes(rule.status) && (
            <HumanApproval
              key={rule.id}
              rule={rule}
              onApproved={updated}
            />
          )}

        {/* Real PayPal Sandbox Payout - Local Development */}
        {!isHostedDemo &&
          rule.status === "USER_APPROVED" && (
            <SandboxPayout
              key={rule.id}
              rule={rule}
              onPayoutSubmitted={updated}
            />
          )}

        {/* Real Payment Tracking - Local Development */}
        {!isHostedDemo && tracking && (
          <PaymentTracking
            key={rule.id}
            rule={rule}
            onRefresh={updated}
          />
        )}

      </div>

      {/* Evidence and Decision History */}
      <details className="audit-disclosure">
        <summary>
          <Icon name="file" size={17} />
          Evidence & decision history
          <Icon name="chevron" size={16} />
        </summary>

        <div className="selected-workflow">
          <SubmissionHistory
            key={`${rule.id}-${rule.status}`}
            ruleId={rule.id}
          />

          <HumanDecisionHistory
            key={`${rule.id}-${rule.status}`}
            ruleId={rule.id}
          />
        </div>
      </details>
    </section>
  );
}
