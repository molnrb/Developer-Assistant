import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export default function AuthScreen({ onAuthSuccess }: { onAuthSuccess: (token: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    setError("");
    const endpoint = mode === "register" ? "/register" : "/login";
    const body = mode === "register"
      ? { username, email, password }
      : { username, password };

    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Something went wrong");

      const token = data.access_token || null;
      if (token) {
        localStorage.setItem("token", token);
        onAuthSuccess(token);
      } else {
        setError("No token returned");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unknown error occurred");
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-900 text-zinc-800 px-4">
      <div className="w-full max-w-md bg-zinc-300 rounded-xl shadow-sm p-8">
        <h1 className="text-2xl font-semibold mb-6 text-center">
          {mode === "login" ? "Sign in to your account" : "Create an account"}
        </h1>

        <div className="flex flex-col gap-4">
          {mode === "register" && (
            <input
              className="w-full rounded-md border border-zinc-300 p-2 focus:outline-none focus:ring-2 focus:ring-zinc-400"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
          <input
            className="w-full rounded-md border border-zinc-300 p-2 focus:outline-none focus:ring-2 focus:ring-zinc-400"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            className="w-full rounded-md border border-zinc-300 p-2 focus:outline-none focus:ring-2 focus:ring-zinc-400"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            onClick={handleSubmit}
            className="w-full bg-zinc-700 text-white rounded-md py-2 hover:bg-zinc-600 transition"
          >
            {mode === "login" ? "Login" : "Register"}
          </button>
          <button
            className="text-center text-sm text-zinc-600 hover:text-zinc-700 underline transition"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login"
              ? "Don't have an account? Register"
              : "Already have an account? Login"}
          </button>
          {error && <p className="text-red-500 text-sm text-center mt-2">{error}</p>}
        </div>
      </div>
    </div>
  );
}
