import { useState } from 'react'

function EvidenceSubmissionForm({ ruleId, onSubmitted }) {
  const [description, setDescription] = useState('')
  const [fileUrl, setFileUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()

    if (!description.trim()) {
      setError('Please describe the completed work.')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(
        `/api/rules/smartpay/${ruleId}/submit`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            description: description.trim(),
            file_url: fileUrl.trim()
          })
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to submit evidence'
        )
      }

      setSuccess('Evidence submitted successfully!')
      setDescription('')
      setFileUrl('')

      onSubmitted?.(data)

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="evidence-section">
      <h2>Submit Payment Evidence</h2>

      <p>
        Provide proof that the payment condition
        has been completed.
      </p>

      <form className="evidence-form" onSubmit={handleSubmit}>
        <label htmlFor="evidence-description">
          Evidence Description
        </label>

        <textarea
          id="evidence-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the work you completed..."
          required
        />

        <label htmlFor="evidence-url">
          Evidence URL (Optional)
        </label>

        <input
          id="evidence-url"
          type="url"
          value={fileUrl}
          onChange={(e) => setFileUrl(e.target.value)}
          placeholder="https://example.com/my-work"
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Submitting...' : 'Submit Evidence'}
        </button>
      </form>

      {success && (
        <p className="success-message" role="status">
          {success}
        </p>
      )}

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}

export default EvidenceSubmissionForm
