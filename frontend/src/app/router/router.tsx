import { Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { useChainPagesContext } from "@/shared/context/ChainPagesContext";
import { staticRoutes, featurePages } from "./routeConfig";

/** Simple loading fallback for lazy-loaded routes */
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-blue-500" />
    </div>
  );
}

export function Router() {
  const chainPagesData = useChainPagesContext();
  const PromptChainPage = featurePages.PromptChainPage;

  // Router is always rendered inside ChainPagesProvider, so null should never occur
  const pages = chainPagesData?.chainPages ?? [];

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Static routes driven by routeConfig */}
        {staticRoutes.map(({ path, component: Component }) => (
          <Route key={path} path={path} element={<Component />} />
        ))}

        {/* Dynamically generated chain page routes */}
        {pages.map((page) => (
          <Route key={page.route} path={page.route} element={<PromptChainPage />} />
        ))}

        {/* Fallback: legacy /prompt-chains/:route pattern */}
        <Route path="/prompt-chains/:route" element={<PromptChainPage />} />

        {/* Catch-all: any unmatched path — PromptChainPage will try to resolve it */}
        <Route path="*" element={<PromptChainPage />} />
      </Routes>
    </Suspense>
  );
}

export default Router;