// Shared colors, spacing and date helpers. Item status colors are defined only here (SR-88).
export const colors = {
  primary: '#1E6FD9',
  background: '#F5F7FA',
  surface: '#FFFFFF',
  text: '#1A1D21',
  textMuted: '#6B7280',
  border: '#E5E7EB',
  danger: '#DC2626',
};

// Item color by days left until its expiration date (SR-123), the same rule for every product:
// the per-product differences are in the expiration date itself (estimated from each product's shelf life)
export const SOON_MAX_DAYS = 3;

export const expiryColors = {
  fresh: '#16A34A', // green: more than SOON_MAX_DAYS days left
  soon: '#EAB308', // yellow: 0 to SOON_MAX_DAYS days left (including today)
  expired: '#DC2626', // red: the date has passed
  unknown: '#9CA3AF', // gray: no expiration date yet
};

// Alert colors by severity (SR-92): the strip color and a light background for the card
export const severityColors = {
  critical: { main: '#DC2626', background: '#FEF2F2' },
  warning: { main: '#D97706', background: '#FFFBEB' },
  info: { main: '#1E6FD9', background: '#EFF6FF' },
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24 };

const MS_PER_DAY = 24 * 60 * 60 * 1000;

// added_at comes from the backend in UTC without a "Z" (e.g. "2026-11-11T09:30:00.123"), so
// the Z is added to parse it as UTC. Returns that moment as a Date.
export function parseAddedAt(addedAt) {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(addedAt) ? addedAt : `${addedAt}Z`);
}

// Calendar days since the item went into the fridge (0 = today), counted at the phone's local midnight.
export function daysInFridge(addedAt) {
  const added = parseAddedAt(addedAt);
  added.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((today - added) / MS_PER_DAY));
}

// Date -> "DD/MM/YYYY" (local day)
export function formatDay(day) {
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}/${day.getFullYear()}`;
}

// Date -> "YYYY-MM-DD" (local day), the format the backend expects
export function toIsoDay(day) {
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  return `${day.getFullYear()}-${mm}-${dd}`;
}

// "YYYY-MM-DD" as a local Date. new Date("YYYY-MM-DD") would parse it as UTC midnight, which can
// shift the day by one depending on the phone's time zone.
export function parseDay(isoDay) {
  const [year, month, day] = isoDay.split('-').map(Number);
  return new Date(year, month - 1, day);
}

// Whole days from today until the expiration date (negative = already expired).
export function daysUntil(isoDay) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((parseDay(isoDay) - today) / MS_PER_DAY);
}

// 'fresh' | 'soon' | 'expired' | 'unknown' for an item's expiration_date
export function getExpiryStatus(expirationDate) {
  if (!expirationDate) return 'unknown';
  const days = daysUntil(expirationDate);
  if (days < 0) return 'expired';
  if (days <= SOON_MAX_DAYS) return 'soon';
  return 'fresh';
}

// The item's main line. Estimated dates start with "≈" so the user knows they are a guess;
// a date the user entered (or OCR read) also shows the date itself.
//   estimated: "≈ 2 days left", "≈ Expires today", "≈ Expired 3 days ago"
//   manual:    "2 days left · 19/11", "Expired yesterday · 16/11"
export function describeExpiry(item) {
  if (!item.expiration_date) return 'No expiry date';
  const days = daysUntil(item.expiration_date);
  let text;
  if (days < -1) text = `Expired ${-days} days ago`;
  else if (days === -1) text = 'Expired yesterday';
  else if (days === 0) text = 'Expires today';
  else if (days === 1) text = '1 day left';
  else text = `${days} days left`;
  if (item.expiration_source === 'estimated') return `≈ ${text}`;
  return `${text} · ${formatDay(parseDay(item.expiration_date)).slice(0, 5)}`;
}

// "Added today", "1 day in fridge", "5 days in fridge"
export function describeTimeInFridge(addedAt) {
  if (!addedAt) return 'Unknown';
  const days = daysInFridge(addedAt);
  if (days === 0) return 'Added today';
  if (days === 1) return '1 day in fridge';
  return `${days} days in fridge`;
}

// Product names from the camera pipeline look like "cottage_cheese" -> "Cottage cheese"
export function formatProductName(name) {
  const words = name.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
