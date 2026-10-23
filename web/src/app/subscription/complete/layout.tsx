import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Subscription status",
  description: "View the status of your Football AI subscription payment.",
  robots: { index: false, follow: false },
};

export default function SubscriptionCompleteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
