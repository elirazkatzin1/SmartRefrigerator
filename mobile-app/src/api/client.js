// Every call to the backend goes through this module (SR-88).
//
// The base URL comes from EXPO_PUBLIC_API_URL (see .env.example). On a real phone
// "localhost" is the phone itself, so set it to the computer's LAN IP, e.g.
// EXPO_PUBLIC_API_URL=http://192.168.1.20:8000/api/v1
export const API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
).replace(/\/+$/, '');

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
