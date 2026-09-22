import React, { useState, useEffect, useCallback } from "react";
import { StyleSheet, Text, View, TextInput, ScrollView, TouchableOpacity, Keyboard, ActivityIndicator } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { useQueryClient } from "@tanstack/react-query";
import { debounce } from "lodash-es";
import { formatDate } from "@/utils";
import type { SearchResultItem } from "@/types";

const SEARCH_TYPES = ["all", "teams", "leagues", "matches", "predictions"];

export default function SearchScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");
  const [results, setResults] = useState<Record<string, SearchResultItem[]>>({});
  const [isSearching, setIsSearching] = useState(false);
  const [history, setHistory] = useState<string[]>([]);

  const search = useCallback(
    debounce(async (q: string, type: string) => {
      if (!q.trim()) {
        setResults({});
        setIsSearching(false);
        return;
      }
      setIsSearching(true);
      try {
        const typeParam = type === "all" ? undefined : type;
        const res = await api.search({ q, type: typeParam, limit: 20 });
        setResults({
          teams: res.teams ?? [],
          leagues: res.leagues ?? [],
          matches: res.matches ?? [],
          predictions: res.predictions ?? [],
        });
      } catch (err) {
        setResults({});
      } finally {
        setIsSearching(false);
      }
    }, 500),
    [],
  );

  useEffect(() => {
    search(query, selectedType);
  }, [query, selectedType, search]);

  const performSearch = (q: string) => {
    setQuery(q);
    if (q.trim() && !history.includes(q.trim())) {
      setHistory((prev) => [q.trim(), ...prev.slice(0, 4)]);
    }
  };

  const clearSearch = () => {
    setQuery("");
    setResults({});
  };

  const clearHistory = () => {
    setHistory([]);
  };

  const allResults = Object.values(results).flat();

  return (
    <View style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}>
      <View style={[styles.searchContainer, { backgroundColor: isDark ? "#0f1f19" : "#ffffff" }]}>
        <TextInput
          style={[
            styles.searchInput,
            {
              backgroundColor: isDark ? "#172b23" : "#eff4f1",
              color: isDark ? "#e7f0eb" : "#121f19",
              placeholderColor: isDark ? "#9eb1a4" : "#617068",
            },
          ]}
          placeholder="Search teams, leagues, matches, predictions..."
          value={query}
          onChangeText={performSearch}
          onSubmitEditing={Keyboard.dismiss}
          returnKeyType="search"
          autoCapitalize="none"
          autoCorrect={false}
        />
        {isSearching && (
          <ActivityIndicator size="small" color={isDark ? "#8bc34a" : "#0d7450"} style={styles.searchIcon} />
        )}
        {!isSearching && query.length > 0 && (
          <TouchableOpacity onPress={clearSearch} style={styles.clearButton}>
            <Text style={{ color: isDark ? "#9eb1a4" : "#617068", fontSize: 16 }}>×</Text>
          </TouchableOpacity>
        )}
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.typeStrip}
        contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }}
      >
        {SEARCH_TYPES.map((type) => (
          <TouchableOpacity
            key={type}
            style={[
              styles.typeButton,
              {
                backgroundColor:
                  selectedType === type
                    ? isDark
                      ? "#8bc34a"
                      : "#0d7450"
                    : isDark
                      ? "#172b23"
                      : "#eff4f1",
              },
            ]}
            onPress={() => {
              setSelectedType(type);
              setQuery("");
              setResults({});
            }}
          >
            <Text
              style={[
                styles.typeButtonText,
                {
                  color:
                    selectedType === type
                      ? "#f7fff7"
                      : isDark
                        ? "#e7f0eb"
                        : "#121f19",
                },
              ]}
            >
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={styles.resultsContainer}>
        {Object.keys(results).length === 0 && !isSearching && query.length === 0 && (
          <View style={styles.historySection}>
            <View style={styles.historyHeader}>
              <Text style={[styles.historyTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                Recent Searches
              </Text>
              {history.length > 0 && (
                <TouchableOpacity onPress={clearHistory}>
                  <Text style={[styles.clearHistory, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                    Clear
                  </Text>
                </TouchableOpacity>
              )}
            </View>
            {history.length === 0 ? (
              <Text style={[styles.historyEmpty, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                No recent searches
              </Text>
            ) : (
              history.map((term) => (
                <TouchableOpacity key={term} onPress={() => performSearch(term)}>
                  <Text style={[styles.historyItem, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    {term}
                  </Text>
                </TouchableOpacity>
              ))
            )}
          </View>
        )}

        {allResults.length === 0 && query.length > 0 && !isSearching && (
          <Text style={[styles.emptyResult, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            No results found for "{query}"
          </Text>
        )}

        {Object.entries(results).map(([category, items]) => {
          if (!items || items.length === 0) return null;
          return (
            <View key={category} style={styles.resultCategory}>
              <Text style={[styles.categoryTitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </Text>
              {items.map((item: SearchResultItem) => (
                <SearchResultItemRow key={`${item.type}-${item.id}`} item={item} isDark={isDark} />
              ))}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

function SearchResultItemRow({ item, isDark }: { item: SearchResultItem; isDark: boolean }) {
  return (
    <TouchableOpacity
      style={[
        styles.resultItem,
        {
          backgroundColor: isDark ? "#0f1f19" : "#ffffff",
          borderColor: isDark ? "#253e33" : "#dce6e0",
        },
      ]}
    >
      <View
        style={[
          styles.resultLogo,
          { backgroundColor: isDark ? "#172b23" : "#eff4f1" },
        ]}
      />
      <View style={styles.resultInfo}>
        <Text
          style={[styles.resultName, { color: isDark ? "#e7f0eb" : "#121f19" }]}
          numberOfLines={1}
        >
          {item.name}
        </Text>
        {item.subtitle && (
          <Text style={[styles.resultSubtitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {item.subtitle}
          </Text>
        )}
        {item.type === "match" && item.kickoff_at && (
          <Text style={[styles.resultDate, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {formatDate(item.kickoff_at)}
          </Text>
        )}
        {item.type === "prediction" && item.generated_at && (
          <Text style={[styles.resultDate, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {formatDate(item.generated_at)}
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 52,
  },
  searchContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(128,128,128,0.2)",
    position: "relative",
  },
  searchInput: {
    flex: 1,
    height: 48,
    paddingHorizontal: 16,
    fontSize: 15,
  },
  searchIcon: {
    marginRight: 8,
  },
  clearButton: {
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  typeStrip: {
    marginBottom: 16,
  },
  typeButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
  },
  typeButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
  resultsContainer: {
    flex: 1,
    paddingHorizontal: 16,
  },
  resultCategory: {
    marginBottom: 24,
  },
  categoryTitle: {
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.3,
    marginBottom: 8,
  },
  resultItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    marginBottom: 6,
  },
  resultLogo: {
    width: 32,
    height: 32,
    borderRadius: 6,
    opacity: 0.5,
  },
  resultInfo: {
    flex: 1,
    gap: 2,
  },
  resultName: {
    fontSize: 14,
    fontWeight: "600",
  },
  resultSubtitle: {
    fontSize: 12,
  },
  resultDate: {
    fontSize: 11,
  },
  historySection: {
    paddingTop: 24,
  },
  historyHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  historyTitle: {
    fontSize: 15,
    fontWeight: "700",
  },
  clearHistory: {
    fontSize: 13,
    fontWeight: "600",
  },
  historyEmpty: {
    fontSize: 14,
    textAlign: "center",
    paddingVertical: 24,
  },
  historyItem: {
    fontSize: 15,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.1)",
  },
  emptyResult: {
    fontSize: 15,
    textAlign: "center",
    paddingVertical: 32,
  },
});
