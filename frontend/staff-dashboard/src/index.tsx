import React from "react";
import ReactDOM from "react-dom";
import {AuthProvider} from "react-oidc-context";
import { User } from "oidc-client-ts";

import reportWebVitals from "./reportWebVitals";
import App from "./App";

ReactDOM.render(
  <React.StrictMode>
    <AuthProvider
      {...OIDC_CONFIG}
      monitorAnonymousSession={false}
      prompt="login"
    >
      <App />
    </AuthProvider>
  </React.StrictMode>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
