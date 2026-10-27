
import { useState } from 'react'

function AIReview({ rule, onReviewed }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canReview = rule.status === 'CONDITION_SUBMITTED'

  async function handleReview() {
    if (!canReview || loading) return

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch(
        `/api/rules/smartpay/${rule.id}/ai-review`,
        { method: 'POST' }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'AI review failed'
        )
      }

      setResult(data)

      // Refresh the rule's status in the dashboard
      await onReviewed?.()

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="ai-review-section">
      <h2>Gemini AI Review</h2>

      <p>
        Let Gemini analyze the submitted evidence
        against the payment condition.
      </p>

      {canReview && (
        <button
          type="button"
          onClick={handleReview}
          disabled={loading}
        >
          {loading ? 'Analyzing Evidence...' : 'Run AI Review'}
        </button>
      )}

      {loading && (
        <p role="status">
          Gemini is analyzing the submitted evidence...
        </p>
      )}

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="ai-result">
          <h3>AI Review Result</h3>

          <p>
            <strong>Recommendation: </strong>
            <span>{result.recommendation}</span>
          </p>

          <p>
            <strong>Confidence: </strong>
            {(result.confidence * 100).toFixed(0)}%
          </p>

          <p>
            <strong>AI Analysis:</strong>
          </p>

          <p>{result.analysis}</p>
        </div>
      )}

      {!canReview && !result && (
        <p>
          Current payment status:
          {' '}{rule.status.replaceAll('_', ' ')}
        </p>
      )}
    </section>
  )
}

export default AIReview
