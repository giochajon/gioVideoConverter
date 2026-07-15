import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Interactive from "./pages/Interactive";
import Batch from "./pages/Batch";
import Settings from "./pages/Settings";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <nav className="nav">
        <NavLink to="/" end>Interactive</NavLink>
        <NavLink to="/batch">Batch</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Interactive />} />
          <Route path="/batch" element={<Batch />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
