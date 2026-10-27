
import { useState } from 'react'

const paymentStatuses = {
  USER_APPROVED: {
    label: 'Ready for Sandbox Payout',
    message: 'Human approval completed. Payment has not been sent.'
  },
  PAYOUT_REQUESTED: {
    label: 'Payout Requested',
    message: 'Your payment request has been recorded.'
  },
  PAYOUT_SUBMITTED: {
    label: 'Payment Processing',
    message: 'PayPal is processing your Sandbox payout.'
  },
  PAYOUT_UNKNOWN: {
    label: 'Payment Status Unconfirmed',
    message: 'The payout outcome requires reconciliation.'
  },
  PAYOUT_DENIED: {
    label: 'Payout Denied',
    message: 'PayPal denied this payout request.'
  },
  PAID: {
    label: 'Payment Completed',
    message: 'PayPal confirmed the Sandbox payment.'
  },
  PAYOUT_FAILED: {
    label: 'Payment Failed',
    message: 'The payout failed.'
  },
  PAYOUT_RETURNED: {
    label: 'Payment Returned',
    message: 'The payout funds were returned.'
  },
  PAYOUT_REFUNDED: {
    label: 'Payment Refunded',
    message: 'The payment was refunded.'
  }
}

function PaymentTracking({ rule, onRefresh }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const current = paymentStatuses[rule.status] || {
    label: rule.status.replaceAll('_', ' '),
    message: 'Check the latest payment status.'
  }

  async function refreshStatus() {
    setLoading(true)
    setError('')

    try {
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Unable to refresh payment status')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="tracking-section">
      <h2>PayPal Payment Tracking</h2>

      <p>Monitor your conditional payment.</p>

      <div className="tracking-card">
        <p><strong>Payment ID:</strong> #{rule.id}</p>

        <p>
          <strong>Amount: </strong>
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: rule.currency
          }).format(rule.amount)}
        </p>

        <p>
          <strong>Status: </strong>
          <span className="tracking-status">
            {current.label}
          </span>
        </p>

        <p>{current.message}</p>
      </div>

      <button
        type="button"
        onClick={refreshStatus}
        disabled={loading}
      >
        {loading ? 'Refreshing...' : 'Refresh Status'}
      </button>

      {error && <p className="error-message" role="alert">{error}</p>}

      <small>
        This refreshes the status saved in PalPay AI.
        It does not initiate another payout or contact PayPal directly.
      </small>
    </section>
  )
}

export default PaymentTracking
