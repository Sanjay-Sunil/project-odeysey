import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import HospitalDashboard from './pages/HospitalDashboard';
import RagSearch from './pages/RagSearch';
import Heatmap from './pages/Heatmap';

/**
 * Hospital configuration — matches AGENT.md §4 seed data exactly.
 */
const HOSPITALS = {
  tvm: {
    id: 'HOSP_TVM_01',
    name: 'General Hospital Thiruvananthapuram',
    short: 'TVM',
  },
  kochi: {
    id: 'HOSP_KCH_01',
    name: 'Kochi Medical Center',
    short: 'Kochi',
  },
  kzk: {
    id: 'HOSP_KZK_01',
    name: 'Kozhikode Care Hospital',
    short: 'KZK',
  },
};

function App() {
  return (
    <BrowserRouter>
      {/* Global Navigation */}
      <header className="app-header" role="banner">
        <div className="container">
          <span className="app-header__title">Rare Disease Federated Detection</span>
          <nav className="app-header__nav" aria-label="Main navigation">
            <NavLink
              to="/hospital/tvm"
              className={({ isActive }) =>
                `app-header__link ${isActive ? 'app-header__link--active' : ''}`
              }
            >
              TVM
            </NavLink>
            <NavLink
              to="/hospital/kochi"
              className={({ isActive }) =>
                `app-header__link ${isActive ? 'app-header__link--active' : ''}`
              }
            >
              Kochi
            </NavLink>
            <NavLink
              to="/hospital/kzk"
              className={({ isActive }) =>
                `app-header__link ${isActive ? 'app-header__link--active' : ''}`
              }
            >
              KZK
            </NavLink>
            <NavLink
              to="/search"
              className={({ isActive }) =>
                `app-header__link ${isActive ? 'app-header__link--active' : ''}`
              }
            >
              Search
            </NavLink>
            <NavLink
              to="/heatmap"
              className={({ isActive }) =>
                `app-header__link ${isActive ? 'app-header__link--active' : ''}`
              }
            >
              Heatmap
            </NavLink>
          </nav>
        </div>
      </header>

      {/* Routes */}
      <main className="page-wrapper" role="main">
        <div className="container">
          <Routes>
            {/* Hospital dashboards — 3 instances, same component, different config */}
            <Route
              path="/hospital/tvm"
              element={<HospitalDashboard hospital={HOSPITALS.tvm} />}
            />
            <Route
              path="/hospital/kochi"
              element={<HospitalDashboard hospital={HOSPITALS.kochi} />}
            />
            <Route
              path="/hospital/kzk"
              element={<HospitalDashboard hospital={HOSPITALS.kzk} />}
            />

            {/* RAG Search */}
            <Route path="/search" element={<RagSearch />} />

            {/* Heatmap */}
            <Route path="/heatmap" element={<Heatmap />} />

            {/* Default redirect */}
            <Route
              path="*"
              element={
                <div className="empty-state">
                  <div className="empty-state__icon">🏥</div>
                  <p className="empty-state__text">
                    Select a hospital dashboard, search, or heatmap from the navigation above.
                  </p>
                </div>
              }
            />
          </Routes>
        </div>
      </main>
    </BrowserRouter>
  );
}

export default App;
