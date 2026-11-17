import { useCallback, useEffect, useRef, useState } from 'react';

// Runs an API function on mount and exposes:
//   data        last successful result (kept while refreshing or after a failed refresh)
//   loading     true only during the first load, before any data arrived
//   refreshing  true while a pull-to-refresh is running
//   error       error of the last request, null if it succeeded
//   reload()    reload with the pull-to-refresh spinner
//   reload({ silent: true })  reload in the background without any spinner
// Pass a stable function (e.g. getInventory) so it does not refetch on every render.
export function useApi(apiFn) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const mounted = useRef(true);
  // Only the newest request may update state, so a slow old response can't overwrite a newer one
  const latestRequest = useRef(0);

  const reload = useCallback(
    async ({ silent = false } = {}) => {
      const requestId = ++latestRequest.current;
      if (!silent) setRefreshing(true);
      try {
        const result = await apiFn();
        if (mounted.current && requestId === latestRequest.current) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted.current && requestId === latestRequest.current) setError(err);
      } finally {
        if (mounted.current && requestId === latestRequest.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [apiFn]
  );

  useEffect(() => {
    mounted.current = true;
    reload({ silent: true });
    return () => {
      mounted.current = false;
    };
  }, [reload]);

  return { data, loading, refreshing, error, reload };
}
