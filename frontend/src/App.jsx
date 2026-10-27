
import { useState } from 'react'
import './App.css'
import CreateSmartPayForm from './components/CreateSmartPayForm'
import EvidenceSubmissionForm from './components/EvidenceSubmissionForm'
import AIReview from './components/AIReview'
import HumanApproval from './components/HumanApproval'
import PaymentTracking from './components/PaymentTracking'
import SandboxPayout from './components/SandboxPayout'

function App() {
  const [ruleId, setRuleId] = useState('3')
  const [rule, setRule] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function fetchSmartPay(event) {
    event.preventDefault()

    setLoading(true)
    setError('')
    setRule(null)

    try {
      const response = await fetch(
        `/api/rules/smartpay/${ruleId}`
      )

      if (!response.ok) {
        throw new Error(
          `Unable to find SmartPay rule (${response.status})`
        )
      }

      const data = await response.json()
      setRule(data)

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  
return (
  <div className="app-layout">

    {/* Sidebar */}
    <aside className="sidebar">
      <h2>PalPay AI</h2>
      <p>Smart Payments</p>

      <nav className="sidebar-nav">
        <span className="active">Dashboard</span>
        <span>Payments</span>
        <span>AI Reviews</span>
        <span>Settings</span>
      </nav>
    </aside>

    {/* Main Dashboard */}
    <main className="main-content">

      <header className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>Manage your intelligent conditional payments.</p>
        </div>
      </header>

      <CreateSmartPayForm
        onCreated={(newRule) => {
          setRuleId(String(newRule.id))
          setRule(newRule)
        }}
      />

      {/* Payment Search */}
      <section className="search-section">
        <h2>Find SmartPay Payment</h2>

        <form onSubmit={fetchSmartPay}>
          <input
            type="number"
            min="1"
            required
            value={ruleId}
            onChange={(e) => setRuleId(e.target.value)}
            placeholder="Enter Rule ID"
            aria-label="SmartPay Rule ID"
          />

          <button type="submit" disabled={loading}>
            {loading ? 'Loading...' : 'Find Payment'}
          </button>
        </form>

        {error && <p role="alert">{error}</p>}
      </section>

      {/* Payment Details */}
      {rule && (
        <section className="payment-card">
          <h2>Payment #{rule.id}</h2>

          <div className="payment-amount">
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: rule.currency
            }).format(rule.amount)}
          </div>

          <p><strong>Recipient:</strong> {rule.recipient_name}</p>

          <p>
            <strong>Status: </strong>
            <span className={`status-badge ${rule.status === 'PAID' ? 'paid' : 'pending'}`}>
              {rule.status.replaceAll('_', ' ')}
            </span>
          </p>

          <p><strong>Description:</strong> {rule.description}</p>
          <p><strong>Condition:</strong> {rule.condition}</p>
        </section>
      )}


{rule && rule.status === 'WAITING_FOR_CONDITION' && (
  <EvidenceSubmissionForm
    ruleId={rule.id}
    onSubmitted={async () => {
      try {
        const response = await fetch(
          `/api/rules/smartpay/${rule.id}`
        )

        if (!response.ok) {
          throw new Error('Unable to refresh payment')
        }

        const updatedRule = await response.json()
        setRule(updatedRule)

      } catch {
        setError(
          'Evidence was submitted, but the payment could not be refreshed. Use Find Payment to reload it.'
        )
      }
    }}
  />
)}


{rule && [
  'CONDITION_SUBMITTED',
  'AWAITING_USER_APPROVAL',
  'AI_REJECTED',
  'NEEDS_REVIEW'
].includes(rule.status) && (
  <AIReview
    key={rule.id}
    rule={rule}
    onReviewed={async () => {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}`
      )

      if (!response.ok) {
        throw new Error('Unable to refresh payment status')
      }

      const updatedRule = await response.json()
      setRule(updatedRule)
    }}
  />
)}


{rule && [
  'AWAITING_USER_APPROVAL',
  'USER_APPROVED'
].includes(rule.status) && (
  <HumanApproval
    key={rule.id}
    rule={rule}
    onApproved={async () => {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}`
      )

      if (!response.ok) {
        throw new Error('Unable to refresh payment')
      }

      const updatedRule = await response.json()
      setRule(updatedRule)
    }}
  />
)}


{rule && [
  'USER_APPROVED',
  'PAYOUT_REQUESTED',
  'PAYOUT_SUBMITTED',
  'PAYOUT_UNKNOWN',
  'PAYOUT_DENIED',
  'PAID',
  'PAYOUT_FAILED',
  'PAYOUT_RETURNED',
  'PAYOUT_REFUNDED'
].includes(rule.status) && (
  <PaymentTracking
    key={rule.id}
    rule={rule}
    onRefresh={async () => {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}`
      )

      if (!response.ok) {
        throw new Error('Unable to retrieve payment status')
      }

      const updatedRule = await response.json()
      setRule(updatedRule)
    }}
  />
)}


{rule && rule.status === 'USER_APPROVED' && (
  <SandboxPayout
    key={rule.id}
    rule={rule}
    onPayoutSubmitted={async () => {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}`
      )

      if (!response.ok) {
        throw new Error('Unable to refresh payment status')
      }

      const updatedRule = await response.json()
      setRule(updatedRule)
    }}
  />
)}

    </main>
  </div>
)

}

export default App
