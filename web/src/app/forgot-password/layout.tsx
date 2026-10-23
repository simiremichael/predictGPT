import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Reset password",
  description: "Request a password reset code for your Football AI account.",
  robots: { index: false, follow: false },
};

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
