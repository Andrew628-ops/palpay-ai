
import { useState } from 'react'
import './App.css'

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
    <main className="dashboard">
      <h1>PalPay AI</h1>
      <p>Intelligent Conditional Payments</p>

      <h2>SmartPay Dashboard</h2>

      <form onSubmit={fetchSmartPay}>
        <label htmlFor="rule-id">SmartPay Rule ID</label>

        <input
          id="rule-id"
          type="number"
          min="1"
          required
          value={ruleId}
          onChange={(e) => setRuleId(e.target.value)}
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Find Payment'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {rule && (
        <section className="payment-card">
          <h2>Payment #{rule.id}</h2>
          <p><strong>Recipient:</strong> {rule.recipient_name}</p>
          <p><strong>Amount:</strong> {rule.amount} {rule.currency}</p>
          <p><strong>Status:</strong> {rule.status}</p>
          <p><strong>Condition:</strong> {rule.condition}</p>
        </section>
      )}
    </main>
  )
}

export default App
