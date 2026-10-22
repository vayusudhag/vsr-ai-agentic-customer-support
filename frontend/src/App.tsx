import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Orders from "./pages/Orders";
import Returns from "./pages/Returns";
import Products from "./pages/Products";
import AdminDashboard from "./pages/AdminDashboard";
import Evaluation from "./pages/Evaluation";

function Guard({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin") return <Navigate to="/app/chat" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/app/chat" element={<Guard><Chat /></Guard>} />
      <Route path="/app/orders" element={<Guard><Orders /></Guard>} />
      <Route path="/app/returns" element={<Guard><Returns /></Guard>} />
      <Route path="/app/products" element={<Guard><Products /></Guard>} />
      <Route path="/admin" element={<Guard admin><AdminDashboard /></Guard>} />
      <Route path="/evaluation" element={<Guard><Evaluation /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
