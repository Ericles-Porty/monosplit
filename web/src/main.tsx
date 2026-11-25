import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { I18nProvider } from "./i18n/I18n";
import "./styles/app.css";
import { ThemeProvider } from "./theme/Theme";

cytoscape.use(fcose);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <App />
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>,
);
