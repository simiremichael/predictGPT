import type { AiEvidenceItem } from "@/types/models";

const EVIDENCE_STATUS_COLORS: Record<string, string> = {
  confirmed: "bg-green-500/10 text-green-600",
  reported: "bg-amber-500/10 text-amber-600",
  probable: "bg-blue-500/10 text-blue-600",
  doubtful: "bg-orange-500/10 text-orange-600",
  unknown: "bg-gray-500/10 text-gray-600",
};

function getStatusBadge(status: string) {
  const normalized = status.toLowerCase();
  const style = EVIDENCE_STATUS_COLORS[normalized] ?? EVIDENCE_STATUS_COLORS.unknown;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {status}
    </span>
  );
}

function getConfidenceBar(confidence: number) {
  const pct = Math.min(100, Math.max(0, confidence * 100));
  const color =
    pct >= 70
      ? "bg-green-500"
      : pct >= 40
        ? "bg-amber-500"
        : "bg-red-500";
  return (
    <div className="mt-1 h-1.5 w-16 rounded-full bg-gray-200">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function formatInjury(item: AiEvidenceItem) {
  return (
    <div className="space-y-1">
      <p className="font-medium">{item.player}</p>
      {item.team && <p className="text-sm text-muted-foreground">Team: {item.team}</p>}
      {item.position && <p className="text-sm text-muted-foreground">Position: {item.position}</p>}
      {item.injury_type && <p className="text-sm text-muted-foreground">Type: {item.injury_type}</p>}
      {item.expected_return && <p className="text-sm text-muted-foreground">Expected return: {item.expected_return}</p>}
    </div>
  );
}

function formatSuspension(item: AiEvidenceItem) {
  return (
    <div className="space-y-1">
      <p className="font-medium">{item.player}</p>
      {item.team && <p className="text-sm text-muted-foreground">Team: {item.team}</p>}
      {item.competition && <p className="text-sm text-muted-foreground">Competition: {item.competition}</p>}
      {item.suspension_status && <p className="text-sm text-muted-foreground">Status: {item.suspension_status}</p>}
      {item.matches_remaining != null && <p className="text-sm text-muted-foreground">Matches remaining: {item.matches_remaining}</p>}
      {item.return_date && <p className="text-sm text-muted-foreground">Return date: {item.return_date}</p>}
    </div>
  );
}

function formatLineup(item: AiEvidenceItem) {
  return (
    <div className="space-y-1">
      {item.team && <p className="font-medium">{item.team}</p>}
      {item.formation && <p className="text-sm text-muted-foreground">Formation: {item.formation}</p>}
      {item.status && getStatusBadge(item.status)}
      {item.unavailable_players && item.unavailable_players.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Unavailable: {item.unavailable_players.join(", ")}
        </p>
      )}
    </div>
  );
}

function formatTeamNews(item: AiEvidenceItem) {
  return (
    <div className="space-y-1">
      {item.team && <p className="font-medium">{item.team}</p>}
      {item.news_type && <p className="text-sm text-muted-foreground">Type: {item.news_type}</p>}
      {item.summary && <p className="text-sm">{item.summary}</p>}
      {item.affected_players && item.affected_players.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Affected players: {item.affected_players.join(", ")}
        </p>
      )}
      {item.tactical_effect && (
        <p className="text-sm text-muted-foreground">Tactical effect: {item.tactical_effect}</p>
      )}
    </div>
  );
}

function renderEvidence(item: AiEvidenceItem) {
  switch (item.kind) {
    case "injury":
      return formatInjury(item);
    case "suspension":
      return formatSuspension(item);
    case "lineup":
      return formatLineup(item);
    case "team_news":
      return formatTeamNews(item);
    default:
      return <p className="text-sm text-muted-foreground">Unknown evidence type</p>;
  }
}

export function AiEvidenceDisplay({
  evidence,
}: {
  evidence: AiEvidenceItem[];
}) {
  if (!evidence.length) return null;

  const grouped = evidence.reduce(
    (acc, item) => {
      const key = item.kind || "other";
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {} as Record<string, AiEvidenceItem[]>,
  );

  const kindLabels: Record<string, string> = {
    injury: "Injuries",
    suspension: "Suspensions",
    lineup: "Lineups",
    team_news: "Team News",
  };

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([kind, items]) => (
        <div key={kind}>
          <h4 className="text-sm font-semibold mb-2">
            {kindLabels[kind] ?? kind}
          </h4>
          <div className="space-y-3">
            {items.map((item, idx) => (
              <div
                key={`${kind}-${idx}`}
                className="rounded-lg border border-gray-200 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">{renderEvidence(item)}</div>
                  <div className="flex flex-shrink-0 flex-col items-end gap-1">
                    {getStatusBadge(item.evidence_status)}
                    {getConfidenceBar(item.confidence ?? 0)}
                    {item.source_ids && item.source_ids.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {item.source_ids.length} source
                        {item.source_ids.length !== 1 ? "s" : ""}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
