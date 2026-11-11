import { useState } from "react";
import Icon from "./Icon";
import { initials, money, statusLabel, statusTone } from "../lib/format";

export default function AgreementPipeline({ rules, loading, onSelect, onCreate, expanded = false }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const filtered = rules.filter(rule => {
    const matchesFilter = filter === "all" || (filter === "approval" ? rule.status === "AWAITING_USER_APPROVAL" : filter === "paid" ? rule.status === "PAID" : !["PAID", "HUMAN_REJECTED"].includes(rule.status));
    return matchesFilter && `${rule.id} ${rule.recipient_name} ${rule.description} ${statusLabel(rule.status)}`.toLowerCase().includes(query.toLowerCase().trim());
  }).sort((a, b) => b.id - a.id);
  const shown = expanded ? filtered : filtered.slice(0, 5);

  return <section className="panel agreement-pipeline" aria-labelledby="pipeline-heading">
    <div className="panel-heading"><div><h2 id="pipeline-heading">Agreement pipeline <span className="count-badge">{rules.length}</span></h2><p>Every commitment, from first promise to final payment.</p></div><button className="icon-button" type="button" aria-label="Create a new agreement" onClick={onCreate}><Icon name="plus" size={18} /></button></div>
    <div className="pipeline-controls"><div className="filter-tabs" aria-label="Filter agreements">{[["all", "All agreements"], ["active", "Active"], ["approval", "Needs approval"], ["paid", "Paid"]].map(([value, label]) => <button type="button" key={value} onClick={() => setFilter(value)} aria-pressed={filter === value} className={filter === value ? "selected" : ""}>{label}</button>)}</div>{expanded && <label className="pipeline-search"><Icon name="search" size={16} /><input type="search" placeholder="Search agreements…" aria-label="Search agreements" value={query} onChange={event => setQuery(event.target.value)} /></label>}</div>
    {loading && !rules.length ? <div className="empty-state"><span className="loading-dot" /><p>Loading your agreements…</p></div> : !shown.length ? <div className="empty-state"><div className="empty-icon"><Icon name="file" size={24} /></div><h3>{rules.length ? "No matching agreements" : "Your next great collaboration starts here."}</h3><p>{rules.length ? "Try another filter or search." : "Create an agreement above to start your payment workflow."}</p>{!rules.length && <button type="button" className="text-button" onClick={onCreate}>Create your first agreement <Icon name="arrow" size={15} /></button>}</div> : <div className="pipeline-table-wrap"><table className="pipeline-table"><thead><tr><th>AGREEMENT / RECIPIENT</th><th>AMOUNT</th><th>STATUS</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{shown.map(rule => <tr key={rule.id}><td><button className="agreement-link" type="button" onClick={() => onSelect(rule)}><span className={`avatar avatar-${rule.id % 4}`}>{initials(rule.recipient_name)}</span><span><strong>{rule.description}</strong><small>#{String(rule.id).padStart(3, "0")}<span>·</span>{rule.recipient_name}</small></span></button></td><td className="table-amount">{money(rule.amount, rule.currency)}</td><td><span className={`status-badge ${statusTone(rule.status)}`}><i />{statusLabel(rule.status)}</span></td><td><button className="icon-button" type="button" aria-label={`Open agreement ${rule.id}`} onClick={() => onSelect(rule)}><Icon name="chevron" size={17} /></button></td></tr>)}</tbody></table></div>}
    {!expanded && filtered.length > 5 && <p className="table-caption">Showing the 5 most recent agreements.</p>}
  </section>;
}
