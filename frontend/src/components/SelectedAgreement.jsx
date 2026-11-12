
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

export default function SelectedAgreement({
  rule,
  onRefresh,
  onClose,
  onError,
}) {
  const tracking = /^(USER_APPROVED|PAYOUT_|PAID)/.test(
    rule.status
  );

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

      <div className="agreement-condition">
        <Icon name="shield" size={19} />

        <div>
          <span>AGREED RELEASE CONDITION</span>
          <p>{rule.condition}</p>
        </div>
      </div>

      <PaymentProgress status={rule.status} />

      <div className="selected-workflow">

        {/* Submit evidence */}
        {rule.status === "WAITING_FOR_CONDITION" && (
          <EvidenceSubmissionForm
            key={rule.id}
            ruleId={rule.id}
            onSubmitted={updated}
          />
        )}

        {/* Gemini AI review */}
        {rule.status !== "WAITING_FOR_CONDITION" && (
          <AIReview
            key={rule.id}
            rule={rule}
            onReviewed={updated}
          />
        )}

        {/* Human review */}
        {rule.status === "NEEDS_REVIEW" && (
          <HumanReviewDecision
            key={rule.id}
            rule={rule}
            onDecided={updated}
          />
        )}

        {/* Evidence resubmission */}
        {[
          "AI_REJECTED",
          "EVIDENCE_REQUESTED",
        ].includes(rule.status) && (
          <EvidenceResubmissionForm
            key={rule.id}
            rule={rule}
            onSubmitted={updated}
          />
        )}

        {/* Real human payment approval */}
        {[
          "AWAITING_USER_APPROVAL",
          "USER_APPROVED",
        ].includes(rule.status) && (
          <HumanApproval
            key={rule.id}
            rule={rule}
            onApproved={updated}
          />
        )}

        {/* Real PayPal Sandbox payout */}
        {rule.status === "USER_APPROVED" && (
          <SandboxPayout
            key={rule.id}
            rule={rule}
            onPayoutSubmitted={updated}
          />
        )}

        {/* Payment tracking */}
        {tracking && (
          <PaymentTracking
            key={rule.id}
            rule={rule}
            onRefresh={updated}
          />
        )}

      </div>

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
