import AsyncStorage from "@react-native-async-storage/async-storage";

export interface SearchHistoryItem {
  id: string;
  query: string;
  timestamp: number;
}

const SEARCH_HISTORY_KEY = "search_history";
const MAX_HISTORY = 20;

export async function getSearchHistory(): Promise<SearchHistoryItem[]> {
  try {
    const raw = await AsyncStorage.getItem(SEARCH_HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SearchHistoryItem[];
  } catch {
    return [];
  }
}

export async function saveSearchHistory(
  items: SearchHistoryItem[],
): Promise<void> {
  try {
    await AsyncStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(items));
  } catch {
    // Ignore
  }
}

export async function addSearchQuery(query: string): Promise<void> {
  const history = await getSearchHistory();
  const existing = history.filter((item) => item.query !== query);
  const newItem: SearchHistoryItem = {
    id: query,
    query,
    timestamp: Date.now(),
  };
  const updated = [newItem, ...existing].slice(0, MAX_HISTORY);
  await saveSearchHistory(updated);
}

export async function clearSearchHistory(): Promise<void> {
  await AsyncStorage.removeItem(SEARCH_HISTORY_KEY);
}

export async function getOfflineCache<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function setOfflineCache<T>(
  key: string,
  value: T,
  ttlMs: number = 300000,
): Promise<void> {
  const payload = {
    data: value,
    cached_at: Date.now(),
    expires_at: Date.now() + ttlMs,
  };
  try {
    await AsyncStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Ignore
  }
}

export async function getOfflineCacheWithExpiry<T>(
  key: string,
): Promise<{ data: T; age: number } | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return null;
    const payload = JSON.parse(raw) as {
      data: T;
      cached_at: number;
      expires_at: number;
    };
    if (Date.now() > payload.expires_at) {
      await AsyncStorage.removeItem(key);
      return null;
    }
    return { data: payload.data, age: Date.now() - payload.cached_at };
  } catch {
    return null;
  }
}
