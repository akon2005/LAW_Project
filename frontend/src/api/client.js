/**
 * LexRAG API Client
 * Handles all communication with the FastAPI backend.
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000,
});

/** POST /api/search — RAG-powered legal research */
export async function searchLegal(params) {
  const response = await api.post('/search', params);
  return response.data;
}

/** POST /api/summarize — Generate AI document summary */
export async function summarizeDoc(docId) {
  const response = await api.post('/summarize', { doc_id: docId });
  return response.data;
}

/** POST /api/similar — Find analogous judgments */
export async function findSimilar(params) {
  const response = await api.post('/similar', params);
  return response.data;
}

/** POST /api/trends — Historical trend analysis */
export async function getTrends(params) {
  const response = await api.post('/trends', params);
  return response.data;
}

/** GET /api/documents — Browse/filter documents */
export async function browseDocuments(params = {}) {
  const response = await api.get('/documents', { params });
  return response.data;
}

/** GET /api/documents/:id — Get single document */
export async function getDocument(docId) {
  const response = await api.get(`/documents/${docId}`);
  return response.data;
}

/** GET /api/sections — List legal sections */
export async function getSections() {
  const response = await api.get('/sections');
  return response.data;
}

/** GET /api/health — Health check */
export async function healthCheck() {
  const response = await api.get('/health');
  return response.data;
}

/** GET /api/reference-data — Get reference datasets for Statutes UI */
export async function getReferenceData() {
  const response = await api.get('/reference-data');
  return response.data;
}

/** GET /api/documents/filters/options — Get actual filter options from DB */
export async function getFilterOptions() {
  const response = await api.get('/documents/filters/options');
  return response.data;
}

export default api;
