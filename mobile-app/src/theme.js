// Shared colors and spacing. Freshness colors are defined only here (SR-88).
export const colors = {
  primary: '#1E6FD9',
  background: '#F5F7FA',
  surface: '#FFFFFF',
  text: '#1A1D21',
  textMuted: '#6B7280',
  border: '#E5E7EB',
  danger: '#DC2626',
};

export const freshnessColors = {
  fresh: '#16A34A', // green: more than 3 days left
  soon: '#EAB308', // yellow: 0-3 days left
  expired: '#DC2626', // red: expiration date already passed
  unknown: '#9CA3AF', // gray: no expiration date detected
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24 };

// Days before expiry that still count as "expiring soon"
export const SOON_THRESHOLD_DAYS = 3;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

// Parses "YYYY-MM-DD" as a local date. new Date("YYYY-MM-DD") would parse it as UTC
// midnight, which can shift the day by one depending on the phone's time zone.
function parseLocalDate(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(year, month - 1, day);
}

// Whole days from today until the expiration date (negative = already expired).
export function daysUntil(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((parseLocalDate(isoDate) - today) / MS_PER_DAY);
}

// Returns 'fresh' | 'soon' | 'expired' | 'unknown' for an expiration date string.
export function getFreshness(expirationDate) {
  if (!expirationDate) return 'unknown';
  const days = daysUntil(expirationDate);
  if (days < 0) return 'expired';
  if (days <= SOON_THRESHOLD_DAYS) return 'soon';
  return 'fresh';
}
