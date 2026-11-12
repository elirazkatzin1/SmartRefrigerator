import { EmptyState } from '../../src/components/StateViews';

// Shopping tab. The list and its backend API come in SR-94.
export default function ShoppingScreen() {
  return <EmptyState icon="cart-outline" title="Your shopping list is empty" />;
}
