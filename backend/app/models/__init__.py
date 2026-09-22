"""SQLAlchemy model registry.

Importing ``models.__init__`` registers every model with the declarative
``Base`` so Alembic's autogenerate and ``Base.metadata.create_all`` see
all tables.

The ``_uuid`` helper is re-exported for use in the match module's
``default=_uuid`` field definitions.
"""
from db.base import Base  # noqa: F401
from models.league import (  # noqa: F401
    League,
    ProviderLeague,
    ProviderTeam,
    Season,
    Team,
)
from models.match import (  # noqa: F401
    ConfirmedLineup,
    HeadToHead,
    Injury,
    Match,
    MatchStatistics,
    ModelMetric,
    ModelVersion,
    NewsItem,
    Odds,
    Player,
    PredictedLineup,
    Prediction,
    PredictionResult,
    PredictionRun,
    PredictionScoreline,
    ProviderPlayer,
    ProviderSyncLog,
    Suspension,
    TeamForm,
    TeamStatistics,
    WebSource,
)
from models.research import (  # noqa: F401
    EvidenceConflict,
    ResearchEvidence,
    ResearchRun,
    WebSourceExtended,
)

__all__ = [
    "Base",
    "League",
    "Season",
    "ProviderLeague",
    "Team",
    "ProviderTeam",
    "Match",
    "MatchStatistics",
    "TeamStatistics",
    "TeamForm",
    "HeadToHead",
    "Player",
    "ProviderPlayer",
    "Injury",
    "Suspension",
    "PredictedLineup",
    "ConfirmedLineup",
    "Odds",
    "WebSource",
    "NewsItem",
    "Prediction",
    "PredictionScoreline",
    "PredictionResult",
    "ModelVersion",
    "ModelMetric",
    "ProviderSyncLog",
    "PredictionRun",
    "EvidenceConflict",
    "ResearchEvidence",
    "ResearchRun",
    "WebSourceExtended",
]
