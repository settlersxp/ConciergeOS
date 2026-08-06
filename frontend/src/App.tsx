import { BrowserRouter } from "react-router-dom";
import { Providers } from "@/app/providers";
import { Router } from "@/app/router";
import { AppLayout } from "@/shared/layout";

export default function App() {
  const basename = import.meta.env.BASE_URL;

  return (
    <BrowserRouter basename={basename}>
      <Providers>
        <AppLayout>
          <Router />
        </AppLayout>
      </Providers>
    </BrowserRouter>
  );
}
