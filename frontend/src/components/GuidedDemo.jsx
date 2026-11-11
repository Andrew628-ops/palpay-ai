import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";

const STEPS = ["The agreement", "Delivery evidence", "AI recommendation", "Your approval", "Payment receipt"];
const CONDITIONS = ["Landing page delivered", "Responsive layout on mobile", "Client accepts the final design"];

function narrationFor(step, scenario, confirmed) {
  return [
    "Welcome to the PalPay AI walkthrough. This example pays Sarah Johnson five hundred US dollars for a landing page. Payment requires delivery, a responsive mobile layout, and client acceptance. All data and results in this walkthrough are simulated.",
    scenario === "complete" ? "The complete delivery includes desktop and mobile testing, plus the client's acceptance. Select See sample review to continue, or choose missing mobile checks to explore an incomplete delivery." : "This delivery is missing mobile testing and client acceptance. Select See sample review to see why payment should stay paused.",
    scenario === "complete" ? "The sample evidence addresses all three release conditions. The AI recommendation is ready for human review. You make the final payment decision." : "More evidence is needed. Mobile testing and client acceptance are missing, so payment stays paused. Revise the evidence to continue.",
    "Review Sarah's sample receiver and the five hundred dollar payout. Check the approval box to authorize the simulated payout, then select Simulate payout.",
    confirmed ? "The simulated payment is confirmed. The walkthrough is complete and your live agreements have not changed. You can now create a real agreement." : "The simulated payout has been submitted and is awaiting confirmation. Submission and confirmation are separate states. Select Simulate PayPal confirmation to finish the example.",
  ][step];
}

export default function GuidedDemo({ onClose, onStart }) {
  const dialogRef = useRef(null);
  const [step, setStep] = useState(0);
  const [scenario, setScenario] = useState("complete");
  const [approved, setApproved] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [audioError, setAudioError] = useState("");
  const utteranceRef = useRef(null);
  const audioSupported = typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

  function stopNarration() {
    utteranceRef.current = null;
    if (audioSupported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function playNarration() {
    stopNarration();
    setAudioError("");
    const utterance = new SpeechSynthesisUtterance(narrationFor(step, scenario, confirmed));
    utterance.lang = "en-US";
    utterance.rate = 0.95;
    utteranceRef.current = utterance;
    utterance.onend = () => { if (utteranceRef.current === utterance) { utteranceRef.current = null; setSpeaking(false); } };
    utterance.onerror = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      setSpeaking(false);
      setAudioError("Narration could not play. Check your device audio and try again.");
    };
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  useEffect(() => {
    return () => {
      utteranceRef.current = null;
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      setSpeaking(false);
    };
  }, [step, scenario, confirmed]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog.open) dialog.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // React StrictMode replays effects. Closing here queues a close event that
    // would dismiss the newly opened walkthrough during that replay.
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  return <dialog className="demo-dialog" ref={dialogRef} onClose={onClose} aria-labelledby="demo-title" onClick={event => { if (event.target === event.currentTarget) dialogRef.current.close(); }}>
    <div className="demo-top"><span className="eyebrow"><Icon name="play" size={13} /> INTERACTIVE WALKTHROUGH</span><button className="icon-button" type="button" aria-label="Close walkthrough" onClick={() => dialogRef.current.close()}><Icon name="close" /></button></div>
    <h2 id="demo-title">One agreement. A clear path to payment.</h2><p className="demo-disclaimer">Sample data and scripted results. No AI or PayPal API calls are made.</p>
    <div className="demo-audio">
      <button className="secondary-button" type="button" disabled={!audioSupported} onClick={speaking ? stopNarration : playNarration}>{speaking ? "Stop narration" : "Play step narration"}</button>
      <p className="demo-helper" role="status">{!audioSupported ? "Audio narration is unavailable in this browser. Follow the written steps below." : audioError || "Listen to this step using your browser’s voice."}</p>
    </div>
    <ol className="demo-steps">{STEPS.map((label, index) => <li key={label} className={index < step ? "complete" : index === step ? "current" : ""} aria-current={index === step ? "step" : undefined}><span>{index < step ? <Icon name="check" size={13} /> : index + 1}</span><small>{label}</small></li>)}</ol>
    <div className="demo-body" aria-live="polite">
      {step === 0 && <><div className="demo-person"><span className="avatar avatar-0">SJ</span><div><strong>Landing page design</strong><small>Sarah Johnson · Freelance designer</small></div><strong className="demo-amount">$500 <small>USD</small></strong></div><div className="demo-quote">“Pay Sarah $500 when the landing page is delivered, works on mobile, and I approve the design.”</div><span className="field-caption">THE RELEASE CONDITIONS</span><ul className="condition-checklist">{CONDITIONS.map((condition, index) => <li key={condition}><span>{index + 1}</span>{condition}</li>)}</ul><div className="inline-note"><Icon name="info" size={17} /><p>In the workspace, you define these conditions. Gemini reviews submitted evidence against them.</p></div></>}
      {step === 1 && <><span className="field-caption">CHOOSE A DELIVERY SCENARIO</span><div className="scenario-options"><button type="button" aria-pressed={scenario === "complete"} className={scenario === "complete" ? "chosen" : ""} onClick={() => setScenario("complete")}><Icon name="check" /><strong>Complete delivery</strong><small>All three conditions addressed.</small></button><button type="button" aria-pressed={scenario === "incomplete"} className={scenario === "incomplete" ? "chosen" : ""} onClick={() => setScenario("incomplete")}><Icon name="clock" /><strong>Missing mobile checks</strong><small>The agent should ask for more.</small></button></div><div className="demo-evidence"><span className="field-caption">SAMPLE RECIPIENT SUBMISSION</span><p>{scenario === "complete" ? "The landing page is delivered. The attached QA notes cover desktop and mobile layouts at 375px, 768px, and 1440px. The client’s acceptance note is included: ‘Final design accepted.’" : "The desktop landing page is delivered. Mobile responsiveness has not been tested yet, and the client has not signed off on the design."}</p></div><p className="demo-helper">The live AI reviews the text you provide. A URL alone does not mean it has inspected the linked work.</p></>}
      {step === 2 && <><div className={`recommendation-heading ${scenario === "complete" ? "success" : "warning"}`}><div className="recommendation-icon"><Icon name={scenario === "complete" ? "sparkles" : "clock"} size={25} /></div><span className="small-tag">SCRIPTED SAMPLE RESULT</span><h3>{scenario === "complete" ? "Ready for your review" : "More evidence needed"}</h3><p>{scenario === "complete" ? "The description addresses each release condition. The final payment decision stays with you." : "Mobile testing and client acceptance are missing. Payment stays paused."}</p></div><ul className="condition-checklist result-checklist">{CONDITIONS.map((condition, index) => <li key={condition}><Icon name={scenario === "complete" || index === 0 ? "check" : "clock"} size={16} /><span>{condition}</span><small>{scenario === "complete" || index === 0 ? "Addressed in sample" : "Missing"}</small></li>)}</ul>{scenario === "incomplete" && <div className="inline-note"><Icon name="shield" size={17} /><p>The request for more evidence keeps an incomplete delivery from reaching payment approval.</p></div>}</>}
      {step === 3 && <><div className="demo-person"><span className="paypal-symbol">P</span><div><strong>Review the sample payout</strong><small>PayPal Sandbox workflow</small></div></div><dl className="demo-receipt"><div><dt>Named recipient</dt><dd>Sarah Johnson</dd></div><div><dt>Sample test receiver</dt><dd>sarah@example.com</dd></div><div><dt>Payment amount</dt><dd>$500.00 USD</dd></div><div><dt>Release conditions</dt><dd className="text-green">Ready for human review</dd></div></dl><label className="demo-consent"><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} /><span>I have reviewed the sample evidence and authorize this simulated payout.</span></label><p className="demo-helper">The live workflow asks you to review the actual Sandbox receiver before sending a payout.</p></>}
      {step === 4 && <><div className={`recommendation-heading ${confirmed ? "success" : "blue"}`}><div className="recommendation-icon"><Icon name={confirmed ? "check" : "clock"} size={26} /></div><span className="small-tag">SIMULATED PAYMENT</span><h3>{confirmed ? "Sample payment confirmed." : "Submitted. Awaiting confirmation."}</h3><p>{confirmed ? "The walkthrough is complete. Your live agreements have not changed." : "A payout request and a confirmed payment are separate states."}</p></div><dl className="demo-receipt"><div><dt>Amount</dt><dd>$500.00 USD</dd></div><div><dt>Recipient</dt><dd>Sarah Johnson</dd></div><div><dt>Status</dt><dd className={confirmed ? "text-green" : "text-amber"}>{confirmed ? "Simulated confirmation" : "Simulated pending"}</dd></div><div><dt>Receipt reference</dt><dd className="mono">DEMO-ONLY-001</dd></div></dl>{!confirmed && <button className="secondary-button full-width" type="button" onClick={() => setConfirmed(true)}><Icon name="refresh" size={16} />Simulate PayPal confirmation</button>}</>}
    </div>
    <div className="demo-footer"><button className="text-button" type="button" onClick={() => { setStep(0); setApproved(false); setConfirmed(false); }}><Icon name="refresh" size={14} />Restart</button><span>{step + 1} / {STEPS.length}</span>{step === 4 ? <button className="primary-button" type="button" onClick={() => { onClose(); onStart(); }}>Create a real agreement<Icon name="arrow" size={16} /></button> : step === 2 && scenario === "incomplete" ? <button className="primary-button" type="button" onClick={() => { setStep(1); setApproved(false); }}>Revise the evidence<Icon name="arrow" size={16} /></button> : <button className="primary-button" type="button" disabled={step === 3 && !approved} onClick={() => setStep(previous => previous + 1)}>{["See the evidence", "See sample review", "Review payout", "Simulate payout"][step]}<Icon name="arrow" size={16} /></button>}</div>
  </dialog>;
}
