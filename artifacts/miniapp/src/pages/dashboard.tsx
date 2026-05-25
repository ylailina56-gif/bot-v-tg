import { useUser } from "@/App";
import {
  useGetBalance, useGetMonthlySummary, useListTransactions, useDeleteTransaction,
  getGetBalanceQueryKey, getGetMonthlySummaryQueryKey, getListTransactionsQueryKey, getGetCategorySummaryQueryKey
} from "@workspace/api-client-react";
import { Card, CardContent } from "@/components/ui/card";
import { format, startOfMonth, eachDayOfInterval } from "date-fns";
import { ArrowDownIcon, ArrowUpIcon, TrendingUp, TrendingDown, Trash2, Download } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function Dashboard() {
  const { userId } = useUser();
  const queryClient = useQueryClient();

  const { data: balance, isLoading: loadingBalance } = useGetBalance({ user_id: userId });
  const { data: monthly, isLoading: loadingMonthly } = useGetMonthlySummary({ user_id: userId });
  const { data: transactions, isLoading: loadingTxs } = useListTransactions({ user_id: userId, limit: 10 });
  const { data: monthTxs } = useListTransactions({ user_id: userId, limit: 100 });
  const deleteTx = useDeleteTransaction();

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(amount);

  const handleDelete = (id: number) => {
    if (confirm("Удалить эту запись?")) {
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

  // Build daily expense chart for current month
  const now = new Date();
  const days = eachDayOfInterval({ start: startOfMonth(now), end: now });
  const chartData = days.map(day => {
    const dayStr = format(day, 'yyyy-MM-dd');
    const expense = monthTxs
      ?.filter(tx => tx.type === 'expense' && tx.created_at.startsWith(dayStr))
      .reduce((sum, tx) => sum + tx.amount, 0) ?? 0;
    return { day: format(day, 'd'), expense };
  });

  // CSV export
  const handleExport = () => {
    if (!monthTxs?.length) return;
    const rows = [
      ['Дата', 'Тип', 'Сумма', 'Категория', 'Заметка'],
      ...monthTxs.map(tx => [
        tx.created_at.slice(0, 10),
        tx.type === 'income' ? 'Доход' : 'Расход',
        tx.amount.toString().replace('.', ','),
        tx.category,
        tx.note ?? '',
      ])
    ];
    const csv = rows.map(r => r.map(v => `"${v}"`).join(';')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `finance_${format(now, 'yyyy-MM')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4 space-y-6 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between py-2">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Обзор</h1>
          <p className="text-sm text-muted-foreground">Ваши финансы</p>
        </div>
        <Button variant="outline" size="sm" className="gap-1.5 h-8" onClick={handleExport} data-testid="button-export-csv">
          <Download className="w-3.5 h-3.5" />
          CSV
        </Button>
      </div>

      {/* Balance Card */}
      <Card className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground border-none shadow-lg">
        <CardContent className="p-6">
          <p className="text-primary-foreground/80 text-sm font-medium">Текущий баланс</p>
          {loadingBalance ? (
            <Skeleton className="h-10 w-40 bg-primary-foreground/20 mt-2" />
          ) : (
            <h2 className="text-4xl font-bold tracking-tight mt-1" data-testid="text-balance">
              {formatCurrency(balance?.balance ?? 0)}
            </h2>
          )}
          <div className="grid grid-cols-2 gap-4 mt-6 pt-4 border-t border-primary-foreground/20">
            <div>
              <div className="flex items-center gap-1 text-primary-foreground/70 text-xs mb-1">
                <ArrowDownIcon className="w-3 h-3" /> Доходы всего
              </div>
              {loadingBalance ? <Skeleton className="h-5 w-20 bg-primary-foreground/20" /> : (
                <p className="font-semibold text-sm">{formatCurrency(balance?.total_income ?? 0)}</p>
              )}
            </div>
            <div>
              <div className="flex items-center gap-1 text-primary-foreground/70 text-xs mb-1">
                <ArrowUpIcon className="w-3 h-3" /> Расходы всего
              </div>
              {loadingBalance ? <Skeleton className="h-5 w-20 bg-primary-foreground/20" /> : (
                <p className="font-semibold text-sm">{formatCurrency(balance?.total_expense ?? 0)}</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Monthly Summary */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Этот месяц</h3>
        <div className="grid grid-cols-2 gap-3">
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-2 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Доходы</p>
                {loadingMonthly ? <Skeleton className="h-5 w-16 mt-1" /> : (
                  <p className="font-semibold text-sm">{formatCurrency(monthly?.income ?? 0)}</p>
                )}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-2 rounded-full bg-rose-100 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400">
                <TrendingDown className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Расходы</p>
                {loadingMonthly ? <Skeleton className="h-5 w-16 mt-1" /> : (
                  <p className="font-semibold text-sm">{formatCurrency(monthly?.expense ?? 0)}</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Daily chart */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Расходы по дням</h3>
        <Card>
          <CardContent className="p-4">
            {loadingTxs ? <Skeleton className="h-36 w-full" /> : (
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                  <XAxis dataKey="day" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={(v: number) => v >= 1000 ? `${Math.round(v / 1000)}к` : String(v)} />
                  <Tooltip
                    formatter={(v: number) => [formatCurrency(v), 'Расходы']}
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid hsl(var(--border))' }}
                  />
                  <Bar dataKey="expense" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} maxBarSize={20} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Transactions */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Последние операции</h3>
        <div className="space-y-2">
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
              <p className="text-sm text-muted-foreground">Нет операций. Добавьте первую!</p>
            </div>
          ) : (
            transactions?.map((tx) => (
              <Card key={tx.id} className="overflow-hidden" data-testid={`card-transaction-${tx.id}`}>
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
                            {format(new Date(tx.created_at), 'd MMM yyyy')}
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
                    <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                      <p className={`font-semibold text-sm ${tx.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : ''}`}>
                        {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount)}
                      </p>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDelete(tx.id)} data-testid={`button-delete-${tx.id}`}>
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
