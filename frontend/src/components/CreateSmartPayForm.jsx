
import { useState } from 'react'

function CreateSmartPayForm({ onCreated }) {
  const [form, setForm] = useState({
    recipient_name: '',
    amount: '',
    currency: 'USD',
    description: '',
    condition: ''
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  function handleChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch('/api/rules/smartpay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...form,
          amount: Number(form.amount)
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to create payment'
        )
      }

      setSuccess(`SmartPay Rule #${data.id} created successfully!`)

      setForm({
        recipient_name: '',
        amount: '',
        currency: 'USD',
        description: '',
        condition: ''
      })

      onCreated?.(data)

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="create-payment">
      <h2>Create SmartPay Payment</h2>

      <form className="create-form" onSubmit={handleSubmit}>
        <label>
          Recipient Name
          <input
            name="recipient_name"
            value={form.recipient_name}
            onChange={handleChange}
            placeholder="John Developer"
            required
          />
        </label>

        <label>
          Amount (USD)
          <input
            name="amount"
            type="number"
            min="0.01"
            step="0.01"
            value={form.amount}
            onChange={handleChange}
            placeholder="100.00"
            required
          />
        </label>

        <label>
          Description
          <input
            name="description"
            value={form.description}
            onChange={handleChange}
            placeholder="Payment for website development"
            required
          />
        </label>

        <label>
          Payment Condition
          <textarea
            name="condition"
            value={form.condition}
            onChange={handleChange}
            placeholder="Describe what must be completed before payment"
            required
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? 'Creating...' : 'Create Payment'}
        </button>
      </form>

      {success && <p className="success-message" role="status">{success}</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  )
}

export default CreateSmartPayForm
