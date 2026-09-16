import React, { useState, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { searchHeatmap } from '../lib/api';

/**
 * Heatmap — Symptom keyword search with map visualization (Module 9).
 * Tag input for keywords → colored cluster markers on Leaflet map of Kerala.
 */
function Heatmap() {
  const [keywords, setKeywords] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [clusters, setClusters] = useState(null);
  const [topMatches, setTopMatches] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  // Add a keyword tag
  const addKeyword = (value) => {
    const trimmed = value.trim().toLowerCase();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
    }
    setInputValue('');
  };

  // Handle keyboard events in tag input
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addKeyword(inputValue);
    }
    if (e.key === 'Backspace' && inputValue === '' && keywords.length > 0) {
      setKeywords(keywords.slice(0, -1));
    }
  };

  // Remove a keyword
  const removeKeyword = (keyword) => {
    setKeywords(keywords.filter((k) => k !== keyword));
  };

  // Search
  const handleSearch = async () => {
    if (keywords.length === 0) return;

    setLoading(true);
    setClusters(null);
    setTopMatches(null);
    setError(null);

    try {
      const data = await searchHeatmap({ symptom_keywords: keywords });
      setClusters(data.clusters || []);
      setTopMatches(data.top_matches_list || []);
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
        Symptom Heatmap
      </h1>

      {/* Tag Input + Search Button */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card__content" style={{ paddingTop: '1.25rem' }}>
          <label className="label" htmlFor="symptom-keyword-input">Symptom Keywords</label>
          <div
            className="tag-input"
            onClick={() => inputRef.current?.focus()}
            role="group"
            aria-label="Symptom keyword tags"
          >
            {keywords.map((kw) => (
              <span key={kw} className="tag-input__tag">
                {kw}
                <button
                  type="button"
                  className="tag-input__remove"
                  onClick={(e) => { e.stopPropagation(); removeKeyword(kw); }}
                  aria-label={`Remove ${kw}`}
                >
                  ×
                </button>
              </span>
            ))}
            <input
              ref={inputRef}
              id="symptom-keyword-input"
              type="text"
              className="tag-input__field"
              placeholder={keywords.length === 0 ? "Type a symptom and press Enter..." : "Add more..."}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
          </div>
        </div>
        <div className="card__footer">
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleSearch}
            disabled={loading || keywords.length === 0}
            aria-label="Search heatmap"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
          {keywords.length > 0 && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => { setKeywords([]); setClusters(null); setTopMatches(null); }}
              aria-label="Clear all keywords"
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div role="alert" style={{ marginBottom: '1.5rem' }}>
          <div className="card" style={{ borderColor: 'var(--destructive)' }}>
            <div className="card__content" style={{ paddingTop: '1.25rem', color: 'var(--destructive)' }}>
              <strong>Error:</strong> {error}
            </div>
          </div>
        </div>
      )}

      {/* Map + Results Layout */}
      <div className="heatmap-layout">
        {/* Map */}
        <div className="map-container">
          <MapContainer
            center={[10.27, 76.4]}
            zoom={7}
            style={{ width: '100%', height: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            />

            {/* Cluster markers */}
            {clusters && clusters.map((cluster, ci) =>
              cluster.points.map((point, pi) => (
                <CircleMarker
                  key={`${ci}-${pi}`}
                  center={[point.lat, point.lng]}
                  radius={10}
                  pathOptions={{
                    color: cluster.color,
                    fillColor: cluster.color,
                    fillOpacity: 0.7,
                    weight: 2,
                  }}
                >
                  <Popup>
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: '0.8125rem' }}>
                      <strong>{cluster.label}</strong>
                      <br />
                      <span style={{ color: '#666' }}>Case: {point.case_id?.slice(0, 8)}...</span>
                    </div>
                  </Popup>
                </CircleMarker>
              ))
            )}
          </MapContainer>
        </div>

        {/* Side Panel — Results List */}
        <div>
          {loading && (
            <div className="results-list" aria-live="polite" aria-busy="true">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton skeleton--card" style={{ height: '5rem' }} />
              ))}
            </div>
          )}

          {!loading && clusters && clusters.length > 0 && (
            <div>
              {/* Legend */}
              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Clusters</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {clusters.map((c, i) => (
                    <span key={i} className="badge badge--default" style={{ borderColor: c.color, borderWidth: '2px' }}>
                      <span style={{
                        display: 'inline-block',
                        width: '0.5rem',
                        height: '0.5rem',
                        borderRadius: '50%',
                        background: c.color,
                        marginRight: '0.25rem',
                      }} />
                      {c.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Top Matches */}
              {topMatches && topMatches.length > 0 && (
                <div className="results-list">
                  <label className="label">Matching Cases</label>
                  {topMatches.map((m, i) => (
                    <div key={i} className="card">
                      <div className="card__content" style={{ paddingTop: '0.75rem', paddingBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 500, marginBottom: '0.25rem' }}>
                          {m.symptom_summary || 'Unknown symptoms'}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>
                          {m.hospital_name} — {m.region}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!loading && clusters !== null && clusters.length === 0 && (
            <div className="empty-state">
              <p className="empty-state__text">No matching cases found for these keywords.</p>
            </div>
          )}

          {!loading && clusters === null && (
            <div className="empty-state">
              <div className="empty-state__icon">🗺️</div>
              <p className="empty-state__text">
                Add symptom keywords above to see matching cases on the map.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Heatmap;
