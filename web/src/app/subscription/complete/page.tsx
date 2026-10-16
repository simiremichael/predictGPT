"use client";

import { Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle, Clock3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/auth";

export default function SubscriptionCompletePage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center">Loading payment status...</div>}>
      <SubscriptionCompleteContent />
    </Suspense>
  );
}

function SubscriptionCompleteContent() {
  const searchParams = useSearchParams();
  const { user, refreshSubscription } = useAuth();
  const [verificationError, setVerificationError] = useState("");
  const transactionId = searchParams.get("transaction_id");
  const txRef = searchParams.get("tx_ref");
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["subscription-status"],
    queryFn: () => api.getSubscriptionStatus(),
    enabled: !!user,
    refetchInterval: (query) => query.state.data?.is_subscribed ? false : 5000,
  });
  const isSubscribed = data?.is_subscribed ?? false;

  useEffect(() => {
    if (!user || !transactionId || !txRef) return;
    let active = true;
    void api.verifySubscriptionPayment(transactionId, txRef)
      .then(async () => {
        await refreshSubscription();
        await refetch();
      })
      .catch((error: unknown) => {
        if (active) setVerificationError(error instanceof Error ? error.message : "Could not verify this payment.");
      });
    return () => { active = false; };
  }, [user?.id, transactionId, txRef, refreshSubscription, refetch]);

  useEffect(() => {
    if (isSubscribed) void refreshSubscription();
  }, [isSubscribed, refreshSubscription]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {isSubscribed ? (
            <CheckCircle className="mx-auto mb-2 h-10 w-10 text-green-500" />
          ) : (
            <Clock3 className="mx-auto mb-2 h-10 w-10 text-primary" />
          )}
          <CardTitle>{isSubscribed ? "Subscription active" : "Checking your payment"}</CardTitle>
          <CardDescription>
            {!user
              ? "Log in to check your subscription status after payment."
              : isSubscribed
              ? "Your premium access is ready."
              : verificationError || "Payment confirmation can take a moment. This page will check again automatically."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {user && !isSubscribed && (
            <Button className="w-full" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
              {isFetching ? "Checking..." : "Check payment status"}
            </Button>
          )}
          {!user && <Button asChild variant="outline" className="w-full"><Link href="/login?redirect=/subscription/complete">Log in</Link></Button>}
          <Button asChild className="w-full"><Link href="/predictions">Go to predictions</Link></Button>
        </CardContent>
      </Card>
    </div>
  );
}
