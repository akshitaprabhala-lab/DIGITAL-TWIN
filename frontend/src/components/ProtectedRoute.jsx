import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (user === null)
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-twin-panel">
        <div className="font-mono text-sm text-twin-muted tracking-widest">INITIALISING TWIN…</div>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
