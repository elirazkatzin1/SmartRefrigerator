// Shared colors and spacing. Item status colors are defined only here (SR-88).
export const colors = {
  primary: '#1E6FD9',
  background: '#F5F7FA',
  surface: '#FFFFFF',
  text: '#1A1D21',
  textMuted: '#6B7280',
  border: '#E5E7EB',
  danger: '#DC2626',
};

// Item color by how long it has been in the fridge.
// Temporary rule for every product; per-category rules (e.g. dairy) are still to be decided.
export const FRESH_MAX_DAYS = 5;

export const fridgeTimeColors = {
  fresh: '#16A34A', // green: in the fridge up to FRESH_MAX_DAYS days
  long: '#EAB308', // yellow: in the fridge longer than that
  unknown: '#9CA3AF', // gray: no added_at
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24 };

const MS_PER_DAY = 24 * 60 * 60 * 1000;

// Calendar days since the item went into the fridge (0 = today).
// added_at comes from the backend in UTC without a "Z" (e.g. "2026-11-11T09:30:00.123"), so
// the Z is added to parse it as UTC; the day boundary is then the phone's local midnight.
export function daysInFridge(addedAt) {
  const utc = /[zZ]|[+-]\d\d:\d\d$/.test(addedAt) ? addedAt : `${addedAt}Z`;
  const added = new Date(utc);
  added.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((today - added) / MS_PER_DAY));
}

// Returns 'fresh' | 'long' | 'unknown' for an item's added_at.
export function getFridgeTimeStatus(addedAt) {
  if (!addedAt) return 'unknown';
  return daysInFridge(addedAt) <= FRESH_MAX_DAYS ? 'fresh' : 'long';
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
