import { useEffect, useState } from "react";
import useAuthStore from "../state/useAuthStore";
import { validateToken } from "./ValidateToken";

export function useSession() {
  const { token, setToken, logout } = useAuthStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const check = async () => {
      const stored = localStorage.getItem("token");
      if (!stored) {
        setChecking(false);
        return;
      }

      const isValid = await validateToken(stored);
      if (isValid) {
        setToken(stored);
      } else {
        localStorage.removeItem("token");
        logout();
      }

      setChecking(false);
    };

    check();
  }, [setToken, logout]);

  const handleAuthSuccess = (newToken: string) => {
    localStorage.setItem("token", newToken);
    setToken(newToken);
  };

  return { token, checking, handleAuthSuccess };
}
