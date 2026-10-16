import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View, ActivityIndicator } from "react-native";
import { Link, useRouter } from "expo-router";
import { Eye, EyeOff } from "lucide-react-native";
import { useTheme } from "@/lib/theme/provider";
import { Colors } from "@/lib/theme/colors";
import { useAuth } from "@/contexts/auth";

export default function SignupScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const colors = theme === "dark" ? Colors.dark : Colors.light;
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setSubmitting(true);
    setError("");
    try {
      await signup(email, password);
      router.replace("/(tabs)/profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create your account. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView style={[styles.screen, { backgroundColor: colors.background }]} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Text style={[styles.title, { color: colors.foreground }]}>Create account</Text>
        <Text style={[styles.subtitle, { color: colors.mutedForeground }]}>Sign up to save your Football AI account.</Text>
        <Text style={[styles.label, { color: colors.foreground }]}>Email</Text>
        <TextInput style={[styles.input, { color: colors.foreground, borderColor: colors.border, backgroundColor: colors.input }]} value={email} onChangeText={setEmail} autoCapitalize="none" autoCorrect={false} keyboardType="email-address" autoComplete="email" textContentType="emailAddress" placeholder="you@example.com" placeholderTextColor={colors.mutedForeground} />
        <Text style={[styles.label, { color: colors.foreground }]}>Password</Text>
        <View style={[styles.passwordWrap, { borderColor: colors.border, backgroundColor: colors.input }]}>
          <TextInput style={[styles.passwordInput, { color: colors.foreground }]} value={password} onChangeText={setPassword} secureTextEntry={!showPassword} autoComplete="new-password" textContentType="newPassword" placeholder="At least 8 characters" placeholderTextColor={colors.mutedForeground} />
          <TouchableOpacity accessibilityRole="button" accessibilityLabel={showPassword ? "Hide password" : "Show password"} onPress={() => setShowPassword((shown) => !shown)} style={styles.eyeButton}>
            {showPassword ? <EyeOff size={20} color={colors.mutedForeground} /> : <Eye size={20} color={colors.mutedForeground} />}
          </TouchableOpacity>
        </View>
        {!!error && <Text accessibilityRole="alert" style={[styles.error, { color: colors.error }]}>{error}</Text>}
        <TouchableOpacity accessibilityRole="button" disabled={submitting || !email || password.length < 8} onPress={submit} style={[styles.primaryButton, { backgroundColor: colors.primary, opacity: submitting || !email || password.length < 8 ? 0.6 : 1 }]}>
          {submitting ? <ActivityIndicator color={colors.primaryForeground} /> : <Text style={[styles.primaryText, { color: colors.primaryForeground }]}>Create account</Text>}
        </TouchableOpacity>
        <Text style={[styles.footer, { color: colors.mutedForeground }]}>Already registered? <Link href="/(auth)/login" style={{ color: colors.primary, fontWeight: "700" }}>Log in</Link></Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, justifyContent: "center", padding: 20 },
  card: { borderWidth: 1, borderRadius: 20, padding: 22, gap: 10 },
  title: { fontSize: 28, fontWeight: "800" },
  subtitle: { fontSize: 14, marginBottom: 12 },
  label: { fontSize: 14, fontWeight: "700", marginTop: 4 },
  input: { minHeight: 48, borderWidth: 1, borderRadius: 12, paddingHorizontal: 14, fontSize: 16 },
  passwordWrap: { minHeight: 48, borderWidth: 1, borderRadius: 12, flexDirection: "row", alignItems: "center" },
  passwordInput: { flex: 1, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  eyeButton: { width: 48, height: 46, alignItems: "center", justifyContent: "center" },
  error: { fontSize: 13 },
  primaryButton: { minHeight: 48, borderRadius: 12, alignItems: "center", justifyContent: "center", marginTop: 8 },
  primaryText: { fontSize: 16, fontWeight: "800" },
  footer: { textAlign: "center", marginTop: 8, fontSize: 14 },
});
