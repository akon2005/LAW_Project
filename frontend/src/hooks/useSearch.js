/**
 * useSearch — Custom hook for the legal research pipeline.
 */
import { useState, useCallback } from 'react';
import { searchLegal } from '../api/client';

export function useSearch() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (params) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await searchLegal(params);
      setResult(data);
      return data;
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Search failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  return { result, loading, error, search, reset };
}
