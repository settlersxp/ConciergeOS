import type { ReactNode } from "react";
import { useMemo } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider } from "@/shared/context/SettingsContext";
import { ChainPagesProvider } from "@/shared/context/ChainPagesContext";
import { useChainPages } from "@/shared/hooks/useChainPages";

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Composed provider wrapper.
 * Data-fetching providers (useChainPages) live outside so the async
 * call is not re-rendered on every children change.
 */
function InnerProviders({ children }: ProvidersProps) {
  const queryClient = useMemo(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000, // 5 minutes
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  }), []);

  return (
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <ChainPagesWrapper>{children}</ChainPagesWrapper>
      </SettingsProvider>
    </QueryClientProvider>
  );
}

/**
 * Bridge: fetches chain pages data (side-effect) and passes it into
 * ChainPagesProvider so consumers can still use the context.
 */
function ChainPagesWrapper({ children }: ProvidersProps) {
  const chainPagesData = useChainPages();

  return (
    <ChainPagesProvider
      chainPages={chainPagesData.chainPages}
      loading={chainPagesData.loading}
      findByRoute={chainPagesData.findByRoute}
    >
      {children}
    </ChainPagesProvider>
  );
}

export { InnerProviders as Providers };