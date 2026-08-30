import { Navigate, Outlet } from "react-router-dom";
import { useRepository } from "@/state/RepositoryContext";

/** Route guard: sends the user back to Connect Repository if nothing is connected yet. */
export function RequireRepository() {
  const { isReady } = useRepository();

  if (!isReady) return <Navigate to="/" replace />;

  return <Outlet />;
}
