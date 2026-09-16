import React, { useState } from 'react';
import { submitToAgent } from '../lib/api';

/**
 * Hospital Dashboard — Doctor-facing agent console (Module 5).
 * Reusable component instantiated 3 times with different hospital configs.
 *
 * Flow: Doctor types symptoms → submits to /agent → sees HPO terms,
 * uniqueness verdict, and push confirmation.
 */
function HospitalDashboard({ hospital }) {
  const [patientRef, setPatientRef] = useState('');
  const [symptomText, setSymptomText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!patientRef.trim() || !symptomText.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const data = await submitToAgent({
        hospital_id: hospital.id,
        patient_ref_id: patientRef.trim(),
        symptom_text: symptomText.trim(),
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <h1 style={{ fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.02em', marginBottom: '1.5rem' }}>
        {hospital.name} — <span style={{ color: 'var(--muted-foreground)' }}>Agent Console</span>
      </h1>

      {/* Input Form */}
      <form onSubmit={handleSubmit} aria-label="Submit patient symptoms">
        <div className="card">
          <div className="card__content" style={{ paddingTop: '1.25rem' }}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="patient-ref" className="label">Patient Reference ID</label>
                <input
                  id="patient-ref"
                  type="text"
                  className="input"
                  placeholder="e.g. PT-2091"
                  value={patientRef}
                  onChange={(e) => setPatientRef(e.target.value)}
                  disabled={loading}
                  aria-required="true"
                />
              </div>
              <div className="form-group" style={{ gridColumn: 'span 1' }}>
                <label htmlFor="symptom-text" className="label">Describe Patient Symptoms</label>
                <textarea
                  id="symptom-text"
                  className="textarea"
                  placeholder="e.g. 45-year-old male presenting with progressive muscle weakness in lower limbs, drooping eyelids bilaterally, and fatigue that worsens significantly through the day..."
                  value={symptomText}
                  onChange={(e) => setSymptomText(e.target.value)}
                  disabled={loading}
                  aria-required="true"
                  rows={5}
                />
              </div>
            </div>
          </div>
          <div className="card__footer">
            <button
              type="submit"
              className="btn btn--primary btn--lg"
              disabled={loading || !patientRef.trim() || !symptomText.trim()}
              aria-label="Submit symptoms to agent"
            >
              {loading ? 'Processing...' : 'Submit to Agent'}
            </button>
          </div>
        </div>
      </form>

      {/* Loading State */}
      {loading && (
        <div style={{ marginTop: '1.5rem' }} aria-live="polite" aria-busy="true">
          <div className="card">
            <div className="card__content" style={{ paddingTop: '1.25rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                <div className="skeleton skeleton--badge" />
                <div className="skeleton skeleton--badge" />
                <div className="skeleton skeleton--badge" />
              </div>
              <div className="skeleton skeleton--text" style={{ width: '60%' }} />
              <div className="skeleton skeleton--text" style={{ width: '80%' }} />
              <div className="skeleton skeleton--text" style={{ width: '40%' }} />
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div style={{ marginTop: '1.5rem' }} role="alert">
          <div className="card" style={{ borderColor: 'var(--destructive)' }}>
            <div className="card__content" style={{ paddingTop: '1.25rem', color: 'var(--destructive)' }}>
              <strong>Error:</strong> {error}
            </div>
          </div>
        </div>
      )}

      {/* Result Card */}
      {result && (
        <div style={{ marginTop: '1.5rem' }} aria-live="polite">
          <div className="card">
            <div className="card__header">
              <h2 className="card__title">Agent Analysis</h2>
              <p className="card__description">HPO terms extracted and uniqueness assessed</p>
            </div>
            <div className="card__content">
              {/* HPO Term Badges */}
              <div style={{ marginBottom: '1rem' }}>
                <label className="label" style={{ marginBottom: '0.5rem' }}>Extracted HPO Terms</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                  {result.hpo_terms && result.hpo_terms.map((term, idx) => (
                    <span key={idx} className="badge badge--default" title={term.id}>
                      {term.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Uniqueness Verdict */}
              <div style={{ marginBottom: '1rem' }}>
                <label className="label" style={{ marginBottom: '0.5rem' }}>Uniqueness Verdict</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className={`badge ${result.is_unique ? 'badge--unique' : 'badge--common'}`}>
                    {result.is_unique ? '● Unique / Rare' : '○ Common'}
                  </span>
                </div>
                {result.reasoning && (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--muted-foreground)', marginTop: '0.5rem', lineHeight: 1.6 }}>
                    {result.reasoning}
                  </p>
                )}
              </div>

              {/* Push Confirmation */}
              {result.pushed_to_global && (
                <div className="push-confirm">
                  <span>✓</span>
                  <span>Pushed to global registry</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HospitalDashboard;
