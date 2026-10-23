"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/auth";

const COUNTRIES = [
  ["DZ", "Algeria"], ["AO", "Angola"], ["BJ", "Benin"], ["BW", "Botswana"],
  ["BF", "Burkina Faso"], ["BI", "Burundi"], ["CV", "Cabo Verde"], ["CM", "Cameroon"],
  ["CF", "Central African Republic"], ["TD", "Chad"], ["KM", "Comoros"], ["CG", "Congo"],
  ["CD", "Democratic Republic of the Congo"], ["CI", "Côte d’Ivoire"], ["DJ", "Djibouti"],
  ["EG", "Egypt"], ["GQ", "Equatorial Guinea"], ["ER", "Eritrea"], ["SZ", "Eswatini"],
  ["ET", "Ethiopia"], ["GA", "Gabon"], ["GM", "Gambia"], ["GH", "Ghana"],
  ["GN", "Guinea"], ["GW", "Guinea-Bissau"], ["KE", "Kenya"], ["LS", "Lesotho"],
  ["LR", "Liberia"], ["LY", "Libya"], ["MG", "Madagascar"], ["MW", "Malawi"],
  ["ML", "Mali"], ["MR", "Mauritania"], ["MU", "Mauritius"], ["MA", "Morocco"],
  ["MZ", "Mozambique"], ["NA", "Namibia"], ["NE", "Niger"], ["NG", "Nigeria"],
  ["RW", "Rwanda"], ["ST", "São Tomé and Príncipe"], ["SN", "Senegal"], ["SC", "Seychelles"],
  ["SL", "Sierra Leone"], ["SO", "Somalia"], ["ZA", "South Africa"], ["SS", "South Sudan"],
  ["SD", "Sudan"], ["TZ", "Tanzania"], ["TG", "Togo"], ["TN", "Tunisia"],
  ["UG", "Uganda"], ["ZM", "Zambia"], ["ZW", "Zimbabwe"],
  ["AL", "Albania"], ["AD", "Andorra"], ["AT", "Austria"], ["BY", "Belarus"],
  ["BE", "Belgium"], ["BA", "Bosnia and Herzegovina"], ["BG", "Bulgaria"], ["HR", "Croatia"],
  ["CY", "Cyprus"], ["CZ", "Czechia"], ["DK", "Denmark"], ["EE", "Estonia"],
  ["FI", "Finland"], ["FR", "France"], ["DE", "Germany"], ["GR", "Greece"],
  ["HU", "Hungary"], ["IS", "Iceland"], ["IE", "Ireland"], ["IT", "Italy"],
  ["XK", "Kosovo"], ["LV", "Latvia"], ["LI", "Liechtenstein"], ["LT", "Lithuania"],
  ["LU", "Luxembourg"], ["MT", "Malta"], ["MD", "Moldova"], ["MC", "Monaco"],
  ["ME", "Montenegro"], ["NL", "Netherlands"], ["MK", "North Macedonia"], ["NO", "Norway"],
  ["PL", "Poland"], ["PT", "Portugal"], ["RO", "Romania"], ["RU", "Russia"],
  ["SM", "San Marino"], ["RS", "Serbia"], ["SK", "Slovakia"], ["SI", "Slovenia"],
  ["ES", "Spain"], ["SE", "Sweden"], ["CH", "Switzerland"], ["TR", "Türkiye"],
  ["UA", "Ukraine"], ["GB", "United Kingdom"], ["VA", "Vatican City"],
  ["AG", "Antigua and Barbuda"], ["AR", "Argentina"], ["BS", "Bahamas"], ["BB", "Barbados"],
  ["BZ", "Belize"], ["BO", "Bolivia"], ["BR", "Brazil"], ["CA", "Canada"],
  ["CL", "Chile"], ["CO", "Colombia"], ["CR", "Costa Rica"], ["CU", "Cuba"],
  ["DM", "Dominica"], ["DO", "Dominican Republic"], ["EC", "Ecuador"], ["SV", "El Salvador"],
  ["GD", "Grenada"], ["GT", "Guatemala"], ["GY", "Guyana"], ["HT", "Haiti"],
  ["HN", "Honduras"], ["JM", "Jamaica"], ["MX", "Mexico"], ["NI", "Nicaragua"],
  ["PA", "Panama"], ["PY", "Paraguay"], ["PE", "Peru"], ["KN", "Saint Kitts and Nevis"],
  ["LC", "Saint Lucia"], ["VC", "Saint Vincent and the Grenadines"], ["SR", "Suriname"],
  ["TT", "Trinidad and Tobago"], ["US", "United States"], ["UY", "Uruguay"], ["VE", "Venezuela"],
  ["AE", "United Arab Emirates"],
  ["OTHER", "Others"],
] as const;

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [country, setCountry] = useState("");
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    if (!country) {
      toast.error("Please select your country");
      return;
    }
    setIsSubmitting(true);
    try {
      await signup(email, password, country);
      toast.success("Account created successfully");
      router.push("/predictions");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Signup failed";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create Account</CardTitle>
          <CardDescription>
            Sign up to see the first 2 predictions for free, or subscribe for
            full access
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="email">
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <div>
              <label
                className="block text-sm font-medium mb-1"
                htmlFor="password"
              >
                Password
              </label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  className="pr-11"
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="country">
                Country <span className="text-destructive">*</span>
              </label>
              <Select value={country} onValueChange={setCountry}>
                <SelectTrigger id="country">
                  <SelectValue placeholder="Select your country" />
                </SelectTrigger>
                <SelectContent className="max-h-[min(20rem,60vh)] overflow-y-auto">
                  {COUNTRIES.map(([code, name]) => (
                    <SelectItem key={code} value={code}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Creating account..." : "Sign up"}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-primary hover:underline"
            >
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
