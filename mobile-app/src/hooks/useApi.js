import { useCallback, useEffect, useRef, useState } from 'react';

// Runs an API function on mount and exposes { data, loading, error, reload }.
// Pass a stable function (e.g. getInventory) so it does not refetch on every render.
export function useApi(apiFn) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFn();
      if (mounted.current) setData(result);
    } catch (err) {
      if (mounted.current) setError(err);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [apiFn]);

  useEffect(() => {
    mounted.current = true;
    reload();
    return () => {
      mounted.current = false;
    };
  }, [reload]);

  return { data, loading, error, reload };
}
