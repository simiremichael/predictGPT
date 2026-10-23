"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, ExternalLink } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth";
import { api } from "@/lib/api";

const FEATURES = [
  "Access to ALL predictions",
  "All match markets (H/D/A, Over 2.5, BTTS)",
  "Top 4 scorelines per match",
  "AI-adjusted predictions with research",
  "Premium match insights",
];

export default function SubscriptionPage() {
  const { user, isSubscribed, loading: authLoading } = useAuth();
  const [initiating, setInitiating] = useState(false);

  const { data: status } = useQuery({
    queryKey: ["subscription-status"],
    queryFn: () => api.getSubscriptionStatus(),
    enabled: !!user && !authLoading,
  });

  const isPremium = status?.is_subscribed ?? isSubscribed;
  const renewalAvailable = status?.renewal_available ?? false;

  const handleSubscribe = async () => {
    if (!user) {
      toast("Please log in to subscribe");
      return;
    }
    if (isPremium) {
      toast("You are already subscribed");
      return;
    }
    setInitiating(true);
    try {
      const result = await api.initiateSubscription();
      if (result.link) {
        window.location.assign(result.link);
      } else {
        toast.success(result.message || "Subscription initiated");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to initiate subscription";
      toast.error(msg);
    } finally {
      setInitiating(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Subscription</CardTitle>
            <CardDescription>You need to log in to manage your subscription.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <a href="/login">Log in</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isPremium && !renewalAvailable) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">
              <CheckCircle className="mx-auto mb-2 h-10 w-10 text-green-500" />
              You are a Premium subscriber
            </CardTitle>
            <CardDescription className="text-center">
              You have full access to all predictions and features.
              {status?.subscription?.current_period_end && (
                <> Your subscription renews or expires on {new Date(status.subscription.current_period_end).toLocaleDateString()}.</>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full" asChild>
                <a href="/predictions">View all predictions</a>
              </Button>
              {renewalAvailable && (
                <Button className="w-full" onClick={handleSubscribe} disabled={initiating}>
                  {initiating ? "Redirecting..." : "Renew subscription"}
                  {!initiating && <ExternalLink className="ml-2 h-4 w-4" />}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Upgrade to Premium</CardTitle>
          <CardDescription>
            Get full access to all football predictions and advanced features.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="text-center">
            <p className="text-4xl font-bold text-primary">
              {status?.subscription_currency === "NGN"
                ? `₦${status?.subscription_price ?? status?.subscription_price_ngn ?? 7000}`
                : `$${status?.subscription_price_usd ?? 5}`}
            </p>
            <p className="text-sm text-muted-foreground">per month</p>
          </div>

          <ul className="space-y-2">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm">{feature}</span>
              </li>
            ))}
          </ul>

          <div className="text-sm text-muted-foreground">
            <p>
              <strong>Free tier:</strong> First 2 predictions per page (no account required).
            </p>
            <p>
              <strong>Premium:</strong> Unlimited access to all predictions with full details.
            </p>
          </div>

          <div className="flex gap-3">
            <Button className="flex-1" onClick={handleSubscribe} disabled={initiating}>
              {initiating ? "Redirecting..." : "Subscribe with Flutterwave"}
              {!initiating && <ExternalLink className="ml-2 h-4 w-4" />}
            </Button>
          </div>

          <p className="text-center text-xs text-muted-foreground">
            Monthly billing through Flutterwave.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
