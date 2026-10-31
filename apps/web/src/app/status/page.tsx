"use client";

import { useEffect, useState } from "react";

export default function StatusPage() {
  const [status, setStatus] = useState("Checking...");

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("Connection failed"));
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 p-12 text-white">
      <h1 className="text-3xl font-bold">
        INTENTRA System Status
      </h1>

      <p className="mt-6 text-lg">
        Backend: {status}
      </p>
    </main>
  );
}
