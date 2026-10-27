
import { useState } from 'react'

function HumanApproval({ rule, onApproved }) {
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canApprove = rule.status === 'AWAITING_USER_APPROVAL'
  const isApproved = rule.status === 'USER_APPROVED'

  async function handleApprove(event) {
    event.preventDefault()

    if (!canApprove || loading || !token.trim()) return

    const confirmed = window.confirm(
      `Approve SmartPay Rule #${rule.id}? ` +
      'This records human approval but does not send payment.'
    )

    if (!confirmed) return

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/approve`,
        {
          method: 'POST',
          headers: {
            'x-approval-token': token.trim()
          }
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to approve payment'
        )
      }

      setToken('')
      setSuccess('Human approval recorded successfully!')

      // Refresh the payment details
      try {
        await onApproved?.()
      } catch {
        setError(
          'Approval was saved, but the dashboard could not refresh. Use Find Payment to reload.'
        )
      }

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="approval-section">
      <h2>Human Payment Approval</h2>

      <p>
        Review the payment details before recording
        your approval.
      </p>

      <div className="approval-details">
        <p><strong>Payment ID:</strong> #{rule.id}</p>
        <p><strong>Recipient:</strong> {rule.recipient_name}</p>
        <p>
          <strong>Amount: </strong>
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: rule.currency
          }).format(rule.amount)}
        </p>
        <p><strong>Condition:</strong> {rule.condition}</p>
      </div>

      {canApprove && (
        <form className="approval-form" onSubmit={handleApprove}>
          <label htmlFor="approval-token">
            Demo Approval Token
          </label>

          <input
            id="approval-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter approval token"
            required
          />

          <button
            type="submit"
            disabled={loading || !token.trim()}
          >
            {loading ? 'Approving...' : 'Approve Payment Rule'}
          </button>

          <small>
            Approval does not automatically send a PayPal payout.
          </small>
        </form>
      )}

      {isApproved && !success &&  (
        <p className="success-message" role="status">
          Human approval recorded. Payment has not yet been sent.
        </p>
      )}

      {success && <p className="success-message" role="status">{success}</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  )
}

export default HumanApproval
