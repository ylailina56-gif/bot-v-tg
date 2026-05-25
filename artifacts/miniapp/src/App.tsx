import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Switch, Route, Router as WouterRouter, Link, useLocation } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Home as HomeIcon, PlusCircle, PieChart } from "lucide-react";
import NotFound from "@/pages/not-found";
import Dashboard from "@/pages/dashboard";
import AddTransaction from "@/pages/add-transaction";
import Categories from "@/pages/categories";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        initDataUnsafe?: {
          user?: {
            id: number;
          };
        };
      };
    };
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

interface UserContextType {
  userId: number;
}

const UserContext = createContext<UserContextType | null>(null);

export function useUser() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser must be used within UserProvider");
  }
  return context;
}

function Layout({ children }: { children: ReactNode }) {
  const [location] = useLocation();

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background max-w-md mx-auto w-full relative shadow-xl overflow-hidden">
      <main className="flex-1 overflow-y-auto pb-20 no-scrollbar">
        {children}
      </main>
      
      <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-card border-t border-border z-50">
        <div className="flex items-center justify-around p-2">
          <Link href="/" className={`flex flex-col items-center p-2 rounded-lg min-w-[64px] transition-colors ${location === '/' ? 'text-primary' : 'text-muted-foreground'}`}>
            <HomeIcon className="w-6 h-6 mb-1" />
            <span className="text-[10px] font-medium">Home</span>
          </Link>
          
          <Link href="/add" className="flex flex-col items-center justify-center -mt-6 rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 w-14 h-14 border-4 border-background transition-transform active:scale-95">
            <PlusCircle className="w-8 h-8" />
          </Link>
          
          <Link href="/categories" className={`flex flex-col items-center p-2 rounded-lg min-w-[64px] transition-colors ${location === '/categories' ? 'text-primary' : 'text-muted-foreground'}`}>
            <PieChart className="w-6 h-6 mb-1" />
            <span className="text-[10px] font-medium">Stats</span>
          </Link>
        </div>
      </nav>
    </div>
  );
}

function Router() {
  return (
    <Layout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/add" component={AddTransaction} />
        <Route path="/categories" component={Categories} />
        <Route component={NotFound} />
      </Switch>
    </Layout>
  );
}

function App() {
  const [userId, setUserId] = useState<number>(1234567);

  useEffect(() => {
    // Initialize Telegram Web App
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.ready();
      const tgUserId = window.Telegram.WebApp.initDataUnsafe?.user?.id;
      if (tgUserId) {
        setUserId(tgUserId);
      }
    }
  }, []);

  return (
    <UserContext.Provider value={{ userId }}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Router />
          </WouterRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </UserContext.Provider>
  );
}

export default App;
