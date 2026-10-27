
import { useState } from 'react'

function SandboxPayout({ rule, onPayoutSubmitted }) {
  const [token, setToken] = useState('')
  const [preview, setPreview] = useState(null)
  const [confirmedEmail, setConfirmedEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function parseResponse(response) {
    const data = await response.json()

    if (!response.ok) {
      throw new Error(
        typeof data.detail === 'string'
          ? data.detail
          : `Request failed (${response.status})`
      )
    }

    return data
  }

  async function loadPreview(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')
    setPreview(null)

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/payout-preview`,
        {
          headers: {
            'x-approval-token': token.trim()
          }
        }
      )

      const data = await parseResponse(response)
      setConfirmedEmail('')
      setPreview(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function sendPayout() {
    if (!preview || sending) return

    const receiver = preview.receiver_email

    if (
      confirmedEmail.trim().toLowerCase()
      !== receiver.trim().toLowerCase()
    ) {
      setError('Sandbox recipient email does not match.')
      return
    }

    const confirmed = window.confirm(
      `Send ${preview.amount} ${preview.currency} ` +
      `to Sandbox account ${receiver}? ` +
      'This will initiate a PayPal Sandbox payout.'
    )

    if (!confirmed) return

    setSending(true)
    setError('')
    setMessage('')

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/pay`,
        {
          method: 'POST',
          headers: {
            'x-approval-token': token.trim(),
            'x-expected-receiver': receiver
          }
        }
      )

      const data = await parseResponse(response)

      setToken('')
      setPreview(null)
      setMessage(
        `Sandbox payout request recorded: ${data.status}`
      )

      try {
        await onPayoutSubmitted?.()
      } catch {
        setError(
          'Payout request was recorded, but the dashboard ' +
          'could not refresh. Reload the payment status.'
        )
      }
    } catch (err) {
      setError(
        `${err.message}. Do not resend until you check ` +
        'the payment status in PalPay AI.'
      )
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="sandbox-section">
      <h2>PayPal Sandbox Payout</h2>

      <p>
        Verify the actual test recipient before
        initiating a Sandbox payment.
      </p>

      <form onSubmit={loadPreview} className="sandbox-form">
        <label htmlFor="sandbox-token">
          Demo Operator Token
        </label>

        <input
          id="sandbox-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(event) => {
            setToken(event.target.value)
            setPreview(null)
            setConfirmedEmail('')
          }}
          placeholder="Enter approval token"
          required
        />

        <button disabled={loading || sending || !token.trim()}>
          {loading ? 'Checking...' : 'Review Sandbox Payout'}
        </button>
      </form>

      {preview && (
        <div className="sandbox-preview">
          <h3>Confirm Payment Details</h3>

          <p><strong>Rule:</strong> #{preview.rule_id}</p>
          <p><strong>Named Recipient:</strong> {preview.recipient_name}</p>

          <p>
            <strong>Amount: </strong>
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: preview.currency
            }).format(preview.amount)}
          </p>

          <p>
            <strong>Actual Sandbox Receiver:</strong>
            {' '}{preview.receiver_email}
          </p>

          <p><strong>Environment:</strong> SANDBOX</p>

          <label htmlFor="confirm-receiver">
            Type the Sandbox receiver email to confirm
          </label>

          <input
            id="confirm-receiver"
            type="email"
            autoComplete="off"
            value={confirmedEmail}
            onChange={(e) => setConfirmedEmail(e.target.value)}
            placeholder="Confirm Sandbox email"
          />

          <button
            type="button"
            className="send-payout-button"
            onClick={sendPayout}
            disabled={
              sending ||
              confirmedEmail.trim().toLowerCase() !==
                preview.receiver_email.trim().toLowerCase()
            }
          >
            {sending ? 'Sending...' : 'Send Sandbox Payout'}
          </button>
        </div>
      )}

      {message && <p role="status">{message}</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  )
}

export default SandboxPayout
