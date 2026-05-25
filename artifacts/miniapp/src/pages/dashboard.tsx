import { useUser } from "@/App";
import { useGetBalance, useGetMonthlySummary, useListTransactions, useDeleteTransaction, getGetBalanceQueryKey, getGetMonthlySummaryQueryKey, getListTransactionsQueryKey, getGetCategorySummaryQueryKey } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { format } from "date-fns";
import { ArrowDownIcon, ArrowUpIcon, TrendingUp, TrendingDown, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";

export default function Dashboard() {
  const { userId } = useUser();
  const queryClient = useQueryClient();
  
  const { data: balance, isLoading: loadingBalance } = useGetBalance({ user_id: userId });
  const { data: monthly, isLoading: loadingMonthly } = useGetMonthlySummary({ user_id: userId });
  const { data: transactions, isLoading: loadingTxs } = useListTransactions({ user_id: userId, limit: 10 });
  const deleteTx = useDeleteTransaction();

  const handleDelete = (id: number) => {
    if (confirm("Are you sure you want to delete this transaction?")) {
      deleteTx.mutate({ id }, {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getGetBalanceQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getGetMonthlySummaryQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getListTransactionsQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getGetCategorySummaryQueryKey({ user_id: userId }) });
        }
      });
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 }).format(amount);
  };

  return (
    <div className="p-4 space-y-6">
      <header className="py-2">
        <h1 className="text-xl font-bold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground">Your financial summary</p>
      </header>

      {/* Balance Card */}
      <Card className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground border-none shadow-lg">
        <CardContent className="p-6">
          <div className="space-y-2">
            <p className="text-primary-foreground/80 text-sm font-medium">Total Balance</p>
            {loadingBalance ? (
              <Skeleton className="h-10 w-32 bg-primary-foreground/20" />
            ) : (
              <h2 className="text-4xl font-bold tracking-tight">
                {formatCurrency(balance?.balance ?? 0)}
              </h2>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-8 pt-4 border-t border-primary-foreground/20">
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-primary-foreground/80 text-xs font-medium">
                <ArrowDownIcon className="w-3 h-3" /> Income
              </div>
              {loadingBalance ? (
                <Skeleton className="h-5 w-20 bg-primary-foreground/20" />
              ) : (
                <p className="font-semibold text-sm">{formatCurrency(balance?.total_income ?? 0)}</p>
              )}
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-primary-foreground/80 text-xs font-medium">
                <ArrowUpIcon className="w-3 h-3" /> Expenses
              </div>
              {loadingBalance ? (
                <Skeleton className="h-5 w-20 bg-primary-foreground/20" />
              ) : (
                <p className="font-semibold text-sm">{formatCurrency(balance?.total_expense ?? 0)}</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Monthly Summary */}
      <div>
        <h3 className="text-sm font-semibold mb-3">This Month</h3>
        <div className="grid grid-cols-2 gap-3">
          <Card className="bg-card">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-2 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Income</p>
                {loadingMonthly ? (
                  <Skeleton className="h-5 w-16 mt-1" />
                ) : (
                  <p className="font-semibold text-sm">{formatCurrency(monthly?.income ?? 0)}</p>
                )}
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-card">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-2 rounded-full bg-rose-100 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400">
                <TrendingDown className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Expense</p>
                {loadingMonthly ? (
                  <Skeleton className="h-5 w-16 mt-1" />
                ) : (
                  <p className="font-semibold text-sm">{formatCurrency(monthly?.expense ?? 0)}</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Recent Transactions */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Recent Transactions</h3>
        </div>
        
        <div className="space-y-3">
          {loadingTxs ? (
            Array(3).fill(0).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                  </div>
                  <Skeleton className="h-5 w-16" />
                </CardContent>
              </Card>
            ))
          ) : transactions?.length === 0 ? (
            <div className="text-center py-10 px-4 bg-muted/30 rounded-xl border border-dashed">
              <p className="text-sm text-muted-foreground">No transactions yet.</p>
            </div>
          ) : (
            transactions?.map((tx) => (
              <Card key={tx.id} className="overflow-hidden">
                <CardContent className="p-0">
                  <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className={`p-2.5 rounded-full flex-shrink-0 ${
                        tx.type === 'income' 
                          ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' 
                          : 'bg-rose-100 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400'
                      }`}>
                        {tx.type === 'income' ? <ArrowDownIcon className="w-4 h-4" /> : <ArrowUpIcon className="w-4 h-4" />}
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{tx.category}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[11px] text-muted-foreground">
                            {format(new Date(tx.created_at), "MMM d, yyyy")}
                          </span>
                          {tx.note && (
                            <>
                              <span className="text-[11px] text-muted-foreground/40">•</span>
                              <span className="text-[11px] text-muted-foreground truncate max-w-[100px]">{tx.note}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 ml-2">
                      <p className={`font-semibold text-sm ${tx.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : 'text-foreground'}`}>
                        {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount)}
                      </p>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0" onClick={() => handleDelete(tx.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
