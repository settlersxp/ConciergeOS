/**
 * Hook that fetches all chain pages (PromptGroups with is_chain_page=true)
 * from the backend on mount and provides them for dynamic route generation.
 */

import { useEffect, useState } from "react";
import { promptGroupsApi } from "../services/promptGroupsApi";
import type { PromptGroup } from "../types/prompt";

export interface ChainPage {
  group: PromptGroup;
  route: string;
}

export function useChainPages() {
  const [chainPages, setChainPages] = useState<ChainPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const groups = await promptGroupsApi.list();
        if (cancelled) return;

        const pages: ChainPage[] = groups
          .filter((g) => g.is_chain_page && g.page_route)
          .map((g) => ({
            group: g,
            route: g.page_route!.startsWith("/") ? g.page_route! : `/${g.page_route!}`,
          }));

        setChainPages(pages);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error("Failed to load chain pages"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * Find a chain page by its route path.
   * Used by PromptChainPage to skip the database lookup when the group is already cached.
   */
  const findByRoute = (route: string) => {
    return chainPages.find((p) => p.route === route)?.group ?? null;
  };

  return { chainPages, loading, error, findByRoute };
}