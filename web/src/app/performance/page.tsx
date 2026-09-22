import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Target, CheckCircle } from "lucide-react";
import type { PredictionStats } from "@/types/models";

export const revalidate = 60;

export const metadata = {
  title: "Performance | Football AI",
  description: "Model performance dashboard and metrics.",
};

export default async function PerformancePage() {
  let data: PredictionStats | null = null;
  let error: string | null = null;

  try {
    data = await api.getPredictionStats();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load performance data";
  }

  if (error) {
    return (
      <Card className="surface-card rounded-[1.75rem]">
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">
            Unable to load performance data. Please ensure the backend is
            running.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="surface-card rounded-[1.75rem]">
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">
            Loading performance data...
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div>
          <p className="section-kicker mb-2">Analytics</p>
          <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
            Model Performance
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Historical performance metrics for the prediction model
          </p>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Predictions"
          value={data.total_predictions.toLocaleString()}
          icon={BarChart3}
        />
        <StatCard
          title="Average Quality"
          value={
            data.average_data_quality !== null &&
            data.average_data_quality !== undefined
              ? `${(data.average_data_quality * 100).toFixed(1)}%`
              : "N/A"
          }
          icon={Target}
        />
        {data.last_prediction_at && (
          <StatCard
            title="Last Prediction"
            value={new Date(data.last_prediction_at).toLocaleDateString()}
            icon={CheckCircle}
          />
        )}
      </div>

      <Card className="surface-card rounded-[1.5rem]">
        <CardHeader>
          <CardTitle className="text-xl font-black tracking-[-0.04em]">
            Predictions by Model
          </CardTitle>
          <CardDescription>
            Distribution of predictions across model versions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Object.entries(data.predictions_by_model || {}).map(
              ([model, count]) => (
                <div
                  key={model}
                  className="flex items-center justify-between rounded-2xl border border-border bg-background/60 px-3 py-3"
                >
                  <span className="text-sm font-medium text-foreground">
                    {model}
                  </span>
                  <Badge
                    variant="secondary"
                    className="rounded-full px-3 py-1 text-xs font-semibold"
                  >
                    {count} predictions
                  </Badge>
                </div>
              ),
            )}
            {Object.keys(data.predictions_by_model || {}).length === 0 && (
              <p className="text-sm text-muted-foreground">
                No predictions recorded
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
}) {
  return (
    <Card className="surface-card rounded-[1.5rem]">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">
              {title}
            </p>
            <p className="mt-2 text-2xl font-black tracking-[-0.06em] text-foreground">
              {value}
            </p>
          </div>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/10">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
