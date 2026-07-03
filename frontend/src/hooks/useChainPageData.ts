/**
 * Hook that manages chain page data loading:
 * - Resolves pageRoute from URL params or pathname
 * - Checks context cache first, falls back to API
 * - Builds step definitions with templates
 *
 * Extracted from PromptChainPage to separate data fetching from rendering.
 */

import { useEffect, useState, useMemo } from "react";
import { useParams, useLocation } from "react-router-dom";
import type { PromptGroup } from "../types/prompt";
import { promptGroupsApi } from "../services/promptGroupsApi";
import { useChainPagesContext } from "../context/ChainPagesContext";
import { buildStepDefinitions, type StepDefinition } from "./useChainExecution";

export function useChainPageData() {
  const { route } = useParams<{ route: string }>();
  const location = useLocation();
  const context = useChainPagesContext();

  // Resolve page_route from either legacy param or direct path
  const pageRoute = useMemo(() => {
    if (route) return route;
    return location.pathname.replace(/\/+$/, "") || "";
  }, [route, location.pathname]);

  // Check context cache first
  const cachedGroup = useMemo(() => {
    return context?.findByRoute(pageRoute) ?? null;
  }, [context, pageRoute]);

  const [group, setGroup] = useState<PromptGroup | null>(cachedGroup);
  const [loading, setLoading] = useState(!cachedGroup);
  const [error, setError] = useState<string | null>(null);
  const [stepDefinitions, setStepDefinitions] = useState<StepDefinition[]>([]);

  // Load group from API if not in cache
  useEffect(() => {
    if (cachedGroup) {
      setGroup(cachedGroup);
      setLoading(false);
      return;
    }

    const loadChainPage = async () => {
      try {
        const groups = await promptGroupsApi.list();
        const page = groups.find((g) => {
          const route = (g.page_route || "").startsWith("/") ? (g.page_route || "") : `/${g.page_route || ""}`;
          return route === pageRoute;
        });
        if (!page) {
          setGroup(null);
          return;
        }
        setGroup(page);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load chain page");
      } finally {
        setLoading(false);
      }
    };
    loadChainPage();
  }, [pageRoute, cachedGroup]);

  // Build step definitions when group is available
  useEffect(() => {
    if (!group) {
      setStepDefinitions([]);
      return;
    }

    let cancelled = false;
    const loadDefs = async () => {
      const defs = await buildStepDefinitions(group.items);
      if (!cancelled) {
        setStepDefinitions(defs);
      }
    };
    loadDefs();
    return () => {
      cancelled = true;
    };
  }, [group]);

  return {
    group,
    loading,
    error,
    stepDefinitions,
    pageRoute,
  };
}