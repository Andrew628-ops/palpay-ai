
import { useState } from "react";
import "./DemoPaymentSimulator.css";

const stages = [
  "Human authorization",
  "Payout submission",
  "Payment confirmation",
];

export default function DemoPaymentSimulator({ rule }) {
  const [step, setStep] = useState(0);

  const messages = [
    "AI has recommended approval. Try the simulated authorization.",
    "Human authorization simulated. No real approval was recorded.",
    "Payout submission simulated. No PayPal API request was made.",
    "Simulation complete. No payment was actually sent or confirmed.",
  ];

  const buttons = [
    "Simulate Human Approval",
    "Simulate Payout Submission",
    "Simulate Payment Confirmation",
  ];

  return (
    <section className="demo-simulator">
      <span className="demo-simulator-label">
        INTERACTIVE DEMO — SIMULATED ONLY
      </span>

      <h2>Experience the Payment Workflow</h2>

      <p>
        Explore what happens after AI recommends approval.
        These actions are visual simulations and do not
        authorize or send real payments.
      </p>

      <div className="demo-simulator-details">
        <p><strong>Agreement:</strong> #{rule.id}</p>
        <p><strong>Recipient:</strong> {rule.recipient_name}</p>
        <p>
          <strong>Amount:</strong>{" "}
          {new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: rule.currency,
          }).format(rule.amount)}
        </p>
      </div>

      <ol className="demo-simulator-stages">
        {stages.map((stage, index) => (
          <li
            key={stage}
            className={step > index ? "completed" : ""}
          >
            <span>{step > index ? "✓" : index + 4}</span>
            <strong>{stage}</strong>
          </li>
        ))}
      </ol>

      <p className="demo-simulator-message" role="status">
        {messages[step]}
      </p>

      {step < 3 ? (
        <button
          type="button"
          className="demo-simulator-button"
          onClick={() => setStep(current => current + 1)}
        >
          {buttons[step]}
        </button>
      ) : (
        <p className="demo-simulator-success">
          ✓ Payment workflow simulation completed!
        </p>
      )}

      {step > 0 && (
        <button
          type="button"
          className="demo-simulator-reset"
          onClick={() => setStep(0)}
        >
          Restart Simulation
        </button>
      )}

      <small>
        Simulation only. The actual agreement remains unchanged.
        Genuine PayPal Sandbox confirmation requires the protected
        payout and reconciliation workflow.
      </small>
    </section>
  );
}
