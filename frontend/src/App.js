import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import Home from "@/pages/Home";
import Intake from "@/pages/Intake";
import Workspace from "@/pages/Workspace";
import Report from "@/pages/Report";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
            <Route path="/intake" element={<ProtectedRoute><Intake /></ProtectedRoute>} />
            <Route path="/intake/:patientId" element={<ProtectedRoute><Intake /></ProtectedRoute>} />
            <Route path="/workspace/:patientId" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
            <Route path="/report/:patientId" element={<ProtectedRoute><Report /></ProtectedRoute>} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" theme="light" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
