/**
 * [INPUT]: 依赖 react-dom/client 的 createRoot，依赖 ./App 与 ./index.css
 * [OUTPUT]: 挂载 React 应用到 #root
 * [POS]: frontend 的渲染入口，整棵组件树的根
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
