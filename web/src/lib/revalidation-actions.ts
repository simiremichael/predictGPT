"use server";

import { revalidateTag } from "next/cache";
import { LEAGUE_TAG, MATCH_TAG, TEAM_TAG, PREDICTION_TAG } from "@/lib/cache-tags";

export async function revalidateMatches() {
  revalidateTag(MATCH_TAG, { expire: 0 });
  revalidateTag(PREDICTION_TAG, { expire: 0 });
}

export async function revalidateLeagues() {
  revalidateTag(LEAGUE_TAG, { expire: 0 });
}

export async function revalidateTeams() {
  revalidateTag(TEAM_TAG, { expire: 0 });
}

export async function revalidatePredictions() {
  revalidateTag(PREDICTION_TAG, { expire: 0 });
}

export async function revalidateAll() {
  revalidateTag(LEAGUE_TAG, { expire: 0 });
  revalidateTag(MATCH_TAG, { expire: 0 });
  revalidateTag(TEAM_TAG, { expire: 0 });
  revalidateTag(PREDICTION_TAG, { expire: 0 });
}
