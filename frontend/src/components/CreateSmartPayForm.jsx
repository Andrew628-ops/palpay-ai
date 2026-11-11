import { useRef, useState } from "react";
import Icon from "./Icon";
import { readResponse } from "../lib/format";

const EMPTY = { recipient_name: "", amount: "", currency: "USD", description: "", condition: "" };
const EXAMPLES = [
  { label: "Website delivery", recipient_name: "Sarah Johnson", amount: "500", description: "Landing page design", condition: "Release payment when the landing page is delivered, the layout is responsive on mobile, and I have approved the final design." },
  { label: "Brand design", recipient_name: "Alex Morgan", amount: "250", description: "Brand identity package", condition: "Release payment when the final logo is delivered in SVG and PNG, the brand color palette is documented, and I have approved the files." },
  { label: "Content creation", recipient_name: "Taylor Lee", amount: "150", description: "Product launch article", condition: "Release payment when a 1,000-word original product article is delivered, requested edits are complete, and I have accepted the final draft." },
];

export default function CreateSmartPayForm({ onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const submitting = useRef(false);

  function handleChange(event) {
    setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
    setSuccess("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting.current) return;
    if (![form.recipient_name, form.description, form.condition].every(value => value.trim())) {
      setError("Add a recipient, agreement title, and release conditions.");
      return;
    }
    if (!Number.isFinite(Number(form.amount)) || Number(form.amount) <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    submitting.current = true;
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const data = await readResponse(await fetch("/api/rules/smartpay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, recipient_name: form.recipient_name.trim(), description: form.description.trim(), condition: form.condition.trim(), amount: Number(form.amount) }),
      }));
      setSuccess(`Agreement #${data.id} created. Next, submit delivery evidence below.`);
      setForm(EMPTY);
      onCreated?.(data);
    } catch (err) {
      setError(err.message || "Unable to create the agreement. Check the backend connection.");
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  }

  return (
    <section className="create-payment panel" id="create-agreement" aria-labelledby="create-heading">
      <div className="panel-heading">
        <div className="heading-icon"><Icon name="sparkles" /></div>
        <div><h2 id="create-heading">A smarter way to agree.</h2><p>Define the outcome. Let AI help review the delivery.</p></div>
        <span className="small-tag">NEW AGREEMENT</span>
      </div>
      <form className="create-form" onSubmit={handleSubmit}>
        <fieldset disabled={loading}>
          <label htmlFor="condition">What needs to happen before payment?</label>
          <textarea id="condition" name="condition" value={form.condition} onChange={handleChange} placeholder="Pay the designer when the landing page is delivered, works on mobile, and I approve the final design…" rows={4} maxLength={4000} required />
          <div className="example-prompts"><span>Try an example</span>{EXAMPLES.map(example => <button key={example.label} className="example-chip" type="button" onClick={() => { setForm({ recipient_name: example.recipient_name, amount: example.amount, description: example.description, condition: example.condition, currency: "USD" }); setError(""); setSuccess(""); }}>{example.label}<Icon name="arrow" size={12} /></button>)}</div>
          <div className="form-row">
            <label>Recipient name<input name="recipient_name" value={form.recipient_name} onChange={handleChange} placeholder="e.g. Sarah Johnson" maxLength={80} required autoComplete="name" /></label>
            <label className="amount-field">Amount <span className="input-currency">USD</span><input name="amount" type="number" min="0.01" step="0.01" value={form.amount} onChange={handleChange} placeholder="500.00" required /></label>
          </div>
          <label>Agreement title<input name="description" value={form.description} onChange={handleChange} placeholder="e.g. Landing page design" maxLength={200} required /></label>
          <div className="create-form-footer"><span><Icon name="shield" size={14} />You always authorize the payout.</span><button className="primary-button" type="submit" disabled={loading}>{loading ? "Creating agreement…" : "Create agreement"}<Icon name="arrow" size={16} /></button></div>
        </fieldset>
      </form>
      {error && <p className="error-message" role="alert">{error}</p>}
      {success && <p className="success-message" role="status"><Icon name="check" size={16} />{success}</p>}
    </section>
  );
}
