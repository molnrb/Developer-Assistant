import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MainLayout from "./MainLayout";
import AuthScreen from "./AuthScreen";
import { useSession } from "./hooks/useSession";

const queryClient = new QueryClient();

function AppContent() {
  const { token, checking, handleAuthSuccess } = useSession();

  if (checking) return <div className="p-4 text-center">Checking session...</div>;
  if (!token) return <AuthScreen onAuthSuccess={handleAuthSuccess} />;

  return <MainLayout />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
