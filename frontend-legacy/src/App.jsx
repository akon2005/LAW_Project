import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Layout/Header';
import Footer from './components/Layout/Footer';
import HomePage from './pages/HomePage';
import DocumentsPage from './pages/PrecedentsPage';
import StatutesArticlesPage from './pages/StatutesArticlesPage';
import AboutPage from './pages/AboutPage';
import { healthCheck } from './api/client';

export default function App() {
  useEffect(() => {
    // Global API health-check on app load
    healthCheck()
      .then((data) => {
        console.log('[API Health] Backend is reachable.', data);
      })
      .catch((err) => {
        console.error('[API Health Error] Failed to connect to backend.', err);
      });
  }, []);

  return (
    <Router>
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/statutes" element={<StatutesArticlesPage />} />
        <Route path="/about" element={<AboutPage />} />
      </Routes>
      <Footer />
    </Router>
  );
}
