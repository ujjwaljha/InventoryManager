import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { installClickFeel } from "./clickFeel";
import "./desktop";
import { LocaleProvider } from "./i18n";
import "./styles.css";

installClickFeel();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LocaleProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </LocaleProvider>
  </React.StrictMode>,
);
