const labels = {
  WAITING_FOR_CONDITION: "Awaiting evidence",
  CONDITION_SUBMITTED: "Ready for AI review",
  NEEDS_REVIEW: "Needs attention",
  EVIDENCE_REQUESTED: "More evidence needed",
  AI_REJECTED: "Evidence declined",
  HUMAN_REJECTED: "Review closed",
  AWAITING_USER_APPROVAL: "Needs your approval",
  USER_APPROVED: "Ready for payout",
  PAYOUT_REQUESTED: "Payout requested",
  PAYOUT_SUBMITTED: "Payout processing",
  PAYOUT_UNKNOWN: "Check payout status",
  PAID: "Payment confirmed",
};

export function statusLabel(status) {
  return labels[status] || String(status || "Unknown").replaceAll("_", " ").toLowerCase();
}

export function statusTone(status) {
  if (status === "PAID") return "success";
  if (["AWAITING_USER_APPROVAL", "NEEDS_REVIEW", "EVIDENCE_REQUESTED", "PAYOUT_UNKNOWN"].includes(status)) return "warning";
  if (/REJECTED|FAILED|DENIED|RETURNED|REFUNDED|REVERSED|CANCELED/.test(status)) return "danger";
  return "blue";
}

export function money(amount, currency = "USD") {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: Number(amount) % 1 === 0 ? 0 : 2 }).format(Number(amount));
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
}

export function initials(name = "") {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0] || "").join("").toUpperCase() || "?";
}

export async function readResponse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The request could not be completed (HTTP ${response.status}).`);
  if (data === null) throw new Error("The API returned an unexpected response. Check that the backend is running.");
  return data;
}
