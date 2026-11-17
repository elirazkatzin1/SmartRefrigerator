import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { API_BASE_URL } from '../api/client';

// The backend's alert stream (SR-92): http://host:8000/api/v1 -> ws://host:8000/api/v1/ws/alerts
export const ALERTS_URL = `${API_BASE_URL.replace(/^http/, 'ws')}/ws/alerts`;

// Wait this long before each reconnect attempt, then keep the last delay
const RETRY_DELAYS_MS = [1000, 2000, 5000, 10000];

// Live list of active fridge alerts, kept in sync over a WebSocket.
//   alerts  the list the server sent last (kept while reconnecting)
//   status  'connecting' | 'connected' | 'disconnected' (and retrying)
// The server sends the whole list on connect and on every change: { type: 'alerts', alerts: [...] }
export function useAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState('connecting');

  useEffect(() => {
    let socket = null;
    let retryTimer = null;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      clearTimeout(retryTimer);
      if (stopped || socket) return;
      socket = new WebSocket(ALERTS_URL);
      socket.onopen = () => {
        attempt = 0;
        setStatus('connected');
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'alerts') setAlerts(message.alerts);
        } catch {
          // Not JSON: ignore, the next message will bring the full list anyway
        }
      };
      // onerror is always followed by onclose, which handles the retry
      socket.onclose = () => {
        socket = null;
        if (stopped) return;
        setStatus('disconnected');
        const delay = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
        attempt += 1;
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    // The phone may cut the connection while the app is in the background; when it comes back,
    // reconnect right away instead of waiting for the next retry
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active' && !socket) {
        attempt = 0;
        setStatus('connecting');
        connect();
      }
    });

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      subscription.remove();
      socket?.close();
    };
  }, []);

  return { alerts, status };
}
