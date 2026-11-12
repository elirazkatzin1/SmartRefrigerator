import { EmptyState } from '../src/components/StateViews';

// Profile screen, reached from Settings. Saving the user's name comes in SR-95.
export default function ProfileScreen() {
  return <EmptyState icon="person-outline" title="Profile" message="Coming in SR-95" />;
}
