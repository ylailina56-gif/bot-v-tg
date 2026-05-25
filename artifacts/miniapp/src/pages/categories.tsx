import { useState } from "react";
import { useUser } from "@/App";
import { useGetCategorySummary } from "@workspace/api-client-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Categories() {
  const { userId } = useUser();
  const [view, setView] = useState<"expenses" | "incomes">("expenses");
  const { data, isLoading } = useGetCategorySummary({ user_id: userId });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 }).format(amount);
  };

  const activeData = view === "expenses" ? data?.expenses : data?.incomes;
  const totalAmount = activeData?.reduce((sum, item) => sum + item.total, 0) || 0;

  return (
    <div className="p-4 space-y-6">
      <header className="py-2">
        <h1 className="text-xl font-bold tracking-tight">Categories</h1>
        <p className="text-sm text-muted-foreground">Breakdown of your spending and income</p>
      </header>

      {/* Toggle View */}
      <div className="flex p-1 bg-muted/50 rounded-xl border">
        <button
          type="button"
          onClick={() => setView("expenses")}
          className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-all ${
            view === "expenses" 
              ? "bg-background text-foreground shadow-sm" 
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Expenses
        </button>
        <button
          type="button"
          onClick={() => setView("incomes")}
          className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-all ${
            view === "incomes" 
              ? "bg-background text-foreground shadow-sm" 
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Income
        </button>
      </div>

      <Card className="border-none shadow-sm bg-card">
        <CardContent className="p-5">
          <div className="mb-6">
            <p className="text-sm text-muted-foreground mb-1">Total {view === 'expenses' ? 'Expenses' : 'Income'}</p>
            {isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <h2 className="text-3xl font-bold">{formatCurrency(totalAmount)}</h2>
            )}
          </div>

          <div className="space-y-5">
            {isLoading ? (
              Array(4).fill(0).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                  <Skeleton className="h-2 w-full rounded-full" />
                </div>
              ))
            ) : activeData?.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">No {view} data available.</p>
              </div>
            ) : (
              activeData?.map((item) => {
                const percentage = totalAmount > 0 ? (item.total / totalAmount) * 100 : 0;
                return (
                  <div key={item.category} className="space-y-2">
                    <div className="flex justify-between items-end">
                      <div>
                        <p className="font-medium text-sm">{item.category}</p>
                        <p className="text-[11px] text-muted-foreground">{percentage.toFixed(1)}%</p>
                      </div>
                      <p className="font-semibold text-sm">{formatCurrency(item.total)}</p>
                    </div>
                    <div className="h-2 w-full bg-muted overflow-hidden rounded-full">
                      <div 
                        className={`h-full rounded-full ${view === 'expenses' ? 'bg-primary' : 'bg-emerald-500'}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
