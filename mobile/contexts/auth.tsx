import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { MobileSubscriptionStatus, MobileUser } from "@/lib/api/client";

interface AuthContextValue {
  user: MobileUser | null;
  isSubscribed: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSubscription: () => Promise<MobileSubscriptionStatus>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MobileUser | null>(null);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshSubscription = useCallback(async () => {
    const status = await api.getSubscriptionStatus();
    setIsSubscribed(status.is_subscribed);
    setUser((current) => current ? { ...current, is_subscribed: status.is_subscribed } : current);
    return status;
  }, []);

  useEffect(() => {
    let active = true;
    const restore = async () => {
      try {
        const token = await AsyncStorage.getItem("auth_token");
        if (token) {
          const currentUser = await api.authGetCurrent();
          if (active) {
            setUser(currentUser);
            setIsSubscribed(currentUser.is_subscribed);
          }
        }
      } catch {
        await AsyncStorage.removeItem("auth_token").catch(() => undefined);
      } finally {
        if (active) setLoading(false);
      }
    };
    void restore();
    return () => { active = false; };
  }, []);

  const authenticate = async (method: typeof api.authLogin, email: string, password: string) => {
    const response = await method(email.trim().toLowerCase(), password);
    await AsyncStorage.setItem("auth_token", response.access_token);
    setUser(response.user);
    setIsSubscribed(response.user.is_subscribed);
  };

  const login = (email: string, password: string) => authenticate(api.authLogin, email, password);
  const signup = (email: string, password: string) => authenticate(api.authRegister, email, password);

  const logout = async () => {
    try {
      await AsyncStorage.removeItem("auth_token");
    } finally {
      setUser(null);
      setIsSubscribed(false);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isSubscribed, loading, login, signup, logout, refreshSubscription }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
