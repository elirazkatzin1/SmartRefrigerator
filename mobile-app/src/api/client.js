import Constants from 'expo-constants';

// Every call to the backend goes through this module (SR-88).

const BACKEND_PORT = 8000;

// The computer running `expo start`, as the phone sees it, e.g. "10.0.0.12".
// Expo Go loaded the app from that computer, and the backend runs on the same one, so this
// follows the computer to whatever network it is on (home WiFi, hotspot...) with no config.
function devServerHost() {
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost;
  const host = hostUri?.split(':')[0];
  // With `expo start --tunnel` the host is an Expo tunnel domain, which does not forward port 8000
  if (!host || host.endsWith('.exp.direct')) return null;
  return host;
}

function resolveBaseUrl() {
  // Explicit override (see .env.example), for a tunnel or a deployed server
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  const host = devServerHost();
  return `http://${host ?? 'localhost'}:${BACKEND_PORT}/api/v1`;
}

export const API_BASE_URL = resolveBaseUrl().replace(/\/+$/, '');

const REQUEST_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    const reason = err.name === 'AbortError' ? 'The server did not respond in time' : 'Cannot reach the server';
    throw new ApiError(`${reason} (${API_BASE_URL})`);
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    // FastAPI puts the error message in "detail"
    let detail = response.statusText;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') detail = data.detail;
    } catch {
      // body was not JSON, keep the status text
    }
    throw new ApiError(`Server error ${response.status}: ${detail}`, response.status);
  }

  return response.status === 204 ? null : response.json();
}

// GET /inventory: every item currently in the fridge
export function getInventory() {
  return request('/inventory');
}

// GET /inventory/expired: items whose expiration date has passed
export function getExpiredInventory() {
  return request('/inventory/expired');
}
