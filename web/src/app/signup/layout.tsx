import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a Football AI account to access match predictions.",
  robots: { index: false, follow: false },
};

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
