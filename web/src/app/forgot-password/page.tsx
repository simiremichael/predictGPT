"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const requestCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.requestPasswordReset(email);
      setCodeSent(true);
      toast.success("If an account exists, a reset code has been sent.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not request a reset code.");
    } finally {
      setBusy(false);
    }
  };

  const submitReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api.resetPassword(email, code, newPassword);
      toast.success(result.message);
      router.push("/login");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not reset your password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Reset your password</CardTitle>
          <CardDescription>We’ll email you a six-digit code that expires after 10 minutes.</CardDescription>
        </CardHeader>
        <CardContent>
          {!codeSent ? (
            <form onSubmit={requestCode} className="space-y-4">
              <label className="block text-sm font-medium" htmlFor="email">Email</label>
              <Input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
              <Button className="w-full" disabled={busy}>{busy ? "Sending code..." : "Send reset code"}</Button>
            </form>
          ) : (
            <form onSubmit={submitReset} className="space-y-4">
              <p className="text-sm text-muted-foreground">Enter the code sent to {email} and choose a new password.</p>
              <Input aria-label="Six-digit reset code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="123456" />
              <Input aria-label="New password" type="password" autoComplete="new-password" minLength={8} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="New password (8+ characters)" />
              <Button className="w-full" disabled={busy || code.length !== 6}>{busy ? "Updating password..." : "Update password"}</Button>
              <Button type="button" variant="outline" className="w-full" disabled={busy} onClick={() => setCodeSent(false)}>Send another code</Button>
            </form>
          )}
          <p className="mt-4 text-center text-sm text-muted-foreground">
            <Link href="/login" className="font-medium text-primary hover:underline">Back to login</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
