import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';

// Carga un recurso de la API con estados de carga, refresco manual y error.
export function useResource(loader, deps = [], initial = null) {
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (mode) => {
    if (mode === 'refresh') setRefreshing(true);
    else if (mode !== 'silent') setLoading(true);
    try {
      const result = await loaderRef.current();
      if (mounted.current) {
        setData(result);
        setError('');
      }
    } catch (err) {
      if (mounted.current && mode !== 'silent' && err.code !== 'SESSION_EXPIRED') setError(err.message || 'No se pudo cargar la información.');
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    run('load');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return {
    data,
    setData,
    loading,
    refreshing,
    error,
    reload: () => run('load'),
    refresh: () => run('refresh'),
    silent: () => run('silent')
  };
}

// Refresca sin spinner cada vez que la pantalla vuelve a estar en foco (excepto la primera carga).
export function useRefreshOnFocus(resource) {
  const first = useRef(true);
  const silentRef = useRef(resource.silent);
  silentRef.current = resource.silent;
  useFocusEffect(
    useCallback(() => {
      if (first.current) {
        first.current = false;
        return;
      }
      silentRef.current();
    }, [])
  );
}
