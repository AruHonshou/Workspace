import { BrowserRouter, HashRouter } from "react-router";
import WorkspaceApp from "./WorkspaceApp";
import { DEMO_MODE } from "./api/client";

export default function App() {
  const Router = DEMO_MODE ? HashRouter : BrowserRouter;
  return <Router><WorkspaceApp /></Router>;
}
