import React, { useState } from 'react';
import { searchSimilarCases } from '../lib/api';

/**
 * RAG Search — Case Reference Search page (Module 7).
 * Clinicians type a natural-language case description,
 * find similar patients across the global registry.
 */
function RagSearch() {
  const [queryText, setQueryText] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!queryText.trim()) return;

    setLoading(true);
    setResults(null);
    setError(null);

    try {
      const data = await searchSimilarCases({ query_text: queryText.trim() });
      setResults(data.results || []);
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
        Case Reference Search
      </h1>

      {/* Search Form */}
      <form onSubmit={handleSearch} aria-label="Search similar cases">
        <div className="card">
          <div className="card__content" style={{ paddingTop: '1.25rem' }}>
            <div className="form-group">
              <label htmlFor="query-text" className="label">Describe a case</label>
              <textarea
                id="query-text"
                className="textarea"
                placeholder="e.g. 45-year-old with progressive muscle weakness, drooping eyelids, and fatigue worsening through the day..."
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                disabled={loading}
                rows={5}
                aria-required="true"
              />
            </div>
          </div>
          <div className="card__footer">
            <button
              type="submit"
              className="btn btn--primary btn--lg"
              disabled={loading || !queryText.trim()}
              aria-label="Search for similar cases"
            >
              {loading ? 'Searching...' : 'Search similar cases'}
            </button>
          </div>
        </div>
      </form>

      {/* Loading State */}
      {loading && (
        <div style={{ marginTop: '1.5rem' }} aria-live="polite" aria-busy="true">
          <div className="results-list">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton skeleton--card" />
            ))}
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

      {/* Results */}
      {results !== null && (
        <div style={{ marginTop: '1.5rem' }} aria-live="polite">
          {results.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">🔍</div>
              <p className="empty-state__text">No similar cases found. Try a different description.</p>
            </div>
          ) : (
            <div className="results-list">
              {results.map((r, idx) => (
                <div key={idx} className="card">
                  <div className="card__content" style={{ paddingTop: '1.25rem' }}>
                    {/* Symptom badges */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginBottom: '0.75rem' }}>
                      {r.symptoms && r.symptoms.map((s, si) => (
                        <span key={si} className="badge badge--default">{s}</span>
                      ))}
                    </div>

                    {/* Similarity score */}
                    <div style={{ marginBottom: '0.75rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>Similarity</span>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                          {(r.similarity_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div
                          className="progress-bar__fill"
                          style={{ width: `${Math.max(0, Math.min(100, r.similarity_score * 100))}%` }}
                        />
                      </div>
                    </div>

                    {/* Hospital info */}
                    <div style={{ fontSize: '0.875rem' }}>
                      <div style={{ fontWeight: 500 }}>{r.hospital_name}</div>
                      <div style={{ color: 'var(--muted-foreground)', fontSize: '0.8125rem' }}>{r.region}</div>
                    </div>
                  </div>
                  <div className="card__footer" style={{ borderTop: '1px solid var(--border)' }}>
                    {r.contact_email && (
                      <a href={`mailto:${r.contact_email}`} className="btn btn--secondary btn--sm">
                        ✉ Email
                      </a>
                    )}
                    {r.contact_phone && (
                      <a href={`tel:${r.contact_phone}`} className="btn btn--secondary btn--sm">
                        📞 Call
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state before search */}
      {!loading && results === null && !error && (
        <div className="empty-state" style={{ marginTop: '2rem' }}>
          <div className="empty-state__icon">🔬</div>
          <p className="empty-state__text">
            Describe a case above to find similar patients across the registry.
          </p>
        </div>
      )}
    </div>
  );
}

export default RagSearch;
