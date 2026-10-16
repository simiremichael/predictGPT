import { useCallback, useState } from "react";
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Link, useFocusEffect } from "expo-router";
import { CheckCircle, ExternalLink } from "lucide-react-native";
import { useAuth } from "@/contexts/auth";
import { api } from "@/lib/api/client";
import { useTheme } from "@/lib/theme/provider";
import { Colors } from "@/lib/theme/colors";

const FEATURES = [
  "Access to all predictions",
  "Match outcome, goals, and BTTS markets",
  "Top scoreline predictions",
  "AI assisted match insights",
];

export default function SubscriptionScreen() {
  const { theme } = useTheme();
  const colors = theme === "dark" ? Colors.dark : Colors.light;
  const { user, isSubscribed, loading: authLoading, refreshSubscription } = useAuth();
  const userId = user?.id;
  const [price, setPrice] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useFocusEffect(useCallback(() => {
    if (!userId) return;
    let checks = 0;
    const refresh = () => {
      void refreshSubscription()
        .then((status) => setPrice(status.subscription_price_usd ?? 5))
        .catch(() => undefined);
    };
    refresh();
    const interval = setInterval(() => {
      checks += 1;
      refresh();
      if (checks >= 12) clearInterval(interval);
    }, 5000);
    return () => clearInterval(interval);
  }, [userId, refreshSubscription]));

  const subscribe = async () => {
    setLoading(true);
    setError("");
    try {
      const checkout = await api.initiateSubscription();
      if (!checkout.link) throw new Error(checkout.message || "Checkout link was not returned.");
      await Linking.openURL(checkout.link);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout. Try again.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) return <View style={[styles.center, { backgroundColor: colors.background }]}><ActivityIndicator color={colors.primary} /></View>;

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.content}>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Text style={[styles.title, { color: colors.foreground }]}>Subscription</Text>
        {!user ? (
          <>
            <Text style={[styles.text, { color: colors.mutedForeground }]}>Log in to manage your subscription or continue to checkout.</Text>
            <Link href="/(auth)/login" asChild><TouchableOpacity style={[styles.button, { backgroundColor: colors.primary }]}><Text style={[styles.buttonText, { color: colors.primaryForeground }]}>Log in</Text></TouchableOpacity></Link>
          </>
        ) : isSubscribed ? (
          <>
            <CheckCircle size={40} color={colors.success} />
            <Text style={[styles.subtitle, { color: colors.foreground }]}>Premium is active</Text>
            <Text style={[styles.text, { color: colors.mutedForeground }]}>Your account has full access to premium predictions.</Text>
          </>
        ) : (
          <>
            <Text style={[styles.subtitle, { color: colors.foreground }]}>Upgrade to Premium</Text>
            <Text style={[styles.price, { color: colors.primary }]}>${price}<Text style={[styles.priceSuffix, { color: colors.mutedForeground }]}> / month</Text></Text>
            {FEATURES.map((feature) => <View key={feature} style={styles.feature}><CheckCircle size={18} color={colors.success} /><Text style={[styles.text, { color: colors.foreground }]}>{feature}</Text></View>)}
            {!!error && <Text accessibilityRole="alert" style={[styles.error, { color: colors.error }]}>{error}</Text>}
            <TouchableOpacity accessibilityRole="button" disabled={loading} onPress={subscribe} style={[styles.button, { backgroundColor: colors.primary, opacity: loading ? 0.6 : 1 }]}>
              {loading ? <ActivityIndicator color={colors.primaryForeground} /> : <><Text style={[styles.buttonText, { color: colors.primaryForeground }]}>Subscribe with Flutterwave</Text><ExternalLink size={16} color={colors.primaryForeground} /></>}
            </TouchableOpacity>
            <Text style={[styles.caption, { color: colors.mutedForeground }]}>Monthly recurring billing via Flutterwave.</Text>
          </>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, justifyContent: "center", padding: 20 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  card: { borderWidth: 1, borderRadius: 20, padding: 22, gap: 14 },
  title: { fontSize: 28, fontWeight: "800" },
  subtitle: { fontSize: 20, fontWeight: "700" },
  text: { fontSize: 15, lineHeight: 22, flexShrink: 1 },
  price: { fontSize: 36, fontWeight: "800" },
  priceSuffix: { fontSize: 15, fontWeight: "400" },
  feature: { flexDirection: "row", alignItems: "center", gap: 9 },
  button: { minHeight: 48, borderRadius: 12, paddingHorizontal: 16, flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 8 },
  buttonText: { fontSize: 15, fontWeight: "800" },
  error: { fontSize: 13 },
  caption: { textAlign: "center", fontSize: 12 },
});
