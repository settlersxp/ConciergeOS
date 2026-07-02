/**
 * Context that provides the loaded chain pages to child components
 * so PromptChainPage can skip redundant database lookups.
 */

import { createContext, useContext, type ReactNode } from "react";
import type { PromptGroup } from "../types/prompt";
import type { ChainPage } from "../hooks/useChainPages";

interface ChainPagesContextValue {
  chainPages: ChainPage[];
  loading: boolean;
  findByRoute: (route: string) => PromptGroup | null;
}

const ChainPagesContext = createContext<ChainPagesContextValue | null>(null);

export function ChainPagesProvider({
  chainPages,
  loading,
  findByRoute,
  children,
}: {
  chainPages: ChainPage[];
  loading: boolean;
  findByRoute: (route: string) => PromptGroup | null;
  children: ReactNode;
}) {
  return (
    <ChainPagesContext.Provider value={{ chainPages, loading, findByRoute }}>
      {children}
    </ChainPagesContext.Provider>
  );
}

/**
 * Hook to access the chain pages cache.
 * Returns null values if used outside a ChainPagesProvider.
 */
export function useChainPagesContext() {
  return useContext(ChainPagesContext);
}