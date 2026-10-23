"use client";

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "@/lib/api";
import type { AuthResponse, User } from "@/types/models";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  isSubscribed: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, country: string) => Promise<void>;
  logout: () => void;
  refreshSubscription: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      setToken(storedToken);
      api
        .authGetCurrent()
        .then((u) => {
          setUser(u);
          setIsSubscribed(u.is_subscribed);
        })
        .catch(() => {
          localStorage.removeItem("auth_token");
          setToken(null);
          setUser(null);
          setIsSubscribed(false);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const refreshSubscription = useCallback(async () => {
    const status = await api.getSubscriptionStatus();
    setIsSubscribed(status.is_subscribed);
    setUser((current) => current ? { ...current, is_subscribed: status.is_subscribed } : current);
  }, []);

  useEffect(() => {
    if (token) void refreshSubscription().catch(() => {});
  }, [token, refreshSubscription]);

  const login = async (email: string, password: string) => {
    const response: AuthResponse = await api.authLogin(email, password);
    localStorage.setItem("auth_token", response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    setIsSubscribed(response.user.is_subscribed);
  };

  const signup = async (email: string, password: string, country: string) => {
    const response: AuthResponse = await api.authRegister(email, password, country);
    localStorage.setItem("auth_token", response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    setIsSubscribed(response.user.is_subscribed);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    setToken(null);
    setUser(null);
    setIsSubscribed(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isSubscribed,
        login,
        signup,
        logout,
        refreshSubscription,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function useAuthRequired() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  if (!ctx.user && !ctx.loading) {
    return { ...ctx, required: true };
  }
  return ctx;
}
