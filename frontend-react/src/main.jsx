import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingEnhanced from "./pages/LandingEnhanced";
import HealPage from "./pages/HealPage";
import Console from "./components/Console";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingEnhanced />} />
        <Route path="/console" element={<Console />} />
        <Route path="/heal" element={<HealPage />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

