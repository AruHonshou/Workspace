import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { migrateBrowserPreferences } from "./app/migrateBrowserPreferences";
import "./styles.css";
import "./styles/workspace.css";
import "./styles/pov.css";
import "./styles/workspaceTokens.css";
import "./styles/product.css";

migrateBrowserPreferences();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
