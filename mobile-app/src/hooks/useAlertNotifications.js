import { useEffect, useRef } from 'react';

import { newEventAlerts } from '../notificationPlan';
import { notifyAlert } from '../notifications';

// Pops up a notification for every door or camera alert that appears while the app runs (SR-93).
// The first list after the app starts is only remembered, not announced: those alerts already
// existed and are on the Home screen. After that, an alert that clears and comes back is announced again.
export function useAlertNotifications(alerts, loaded) {
  const seenIds = useRef(null);

  useEffect(() => {
    if (!loaded) return;
    if (seenIds.current !== null) {
      for (const alert of newEventAlerts(alerts, seenIds.current)) notifyAlert(alert);
    }
    seenIds.current = new Set(alerts.map((alert) => alert.id));
  }, [alerts, loaded]);
}
