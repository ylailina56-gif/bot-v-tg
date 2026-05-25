import { useState } from "react";
import { useUser } from "@/App";
import {
  useGetLimits, useSetLimit, useDeleteLimit,
  useGetCategorySummary,
  getGetLimitsQueryKey,
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Trash2, Plus, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const formatCurrency = (v: number) =>
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(v);

export default function Limits() {
  const { userId } = useUser();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: limits, isLoading: loadingLimits } = useGetLimits({ user_id: userId });
  const { data: categoryData } = useGetCategorySummary({ user_id: userId });
  const setLimit = useSetLimit();
  const deleteLimit = useDeleteLimit();

  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [showForm, setShowForm] = useState(false);

  // Build a map of current month's expenses per category
  const spentMap: Record<string, number> = {};
  categoryData?.expenses?.forEach(e => { spentMap[e.category] = e.total; });

  const handleAdd = () => {
    if (!category.trim()) {
      toast({ title: "Введите категорию", variant: "destructive" });
      return;
    }
    const val = Number(amount);
    if (!amount || isNaN(val) || val <= 0) {
      toast({ title: "Введите корректную сумму", variant: "destructive" });
      return;
    }
    setLimit.mutate(
      { data: { user_id: userId, category: category.trim(), monthly_limit: val } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getGetLimitsQueryKey({ user_id: userId }) });
          toast({ title: "Лимит сохранён" });
          setCategory("");
          setAmount("");
          setShowForm(false);
        },
        onError: () => toast({ title: "Ошибка при сохранении", variant: "destructive" }),
      }
    );
  };

  const handleDelete = (id: number) => {
    deleteLimit.mutate({ id }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetLimitsQueryKey({ user_id: userId }) });
        toast({ title: "Лимит удалён" });
      },
    });
  };

  return (
    <div className="p-4 space-y-6 pb-24">
      <div className="flex items-center justify-between py-2">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Лимиты</h1>
          <p className="text-sm text-muted-foreground">Контроль расходов по категориям</p>
        </div>
        <Button size="sm" className="gap-1.5 h-8" onClick={() => setShowForm(v => !v)}>
          <Plus className="w-3.5 h-3.5" />
          Добавить
        </Button>
      </div>

      {/* Add form */}
      {showForm && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="p-4 space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Категория</Label>
              <Input
                placeholder="Еда, Транспорт, ЖКХ..."
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="h-10"
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Лимит в месяц (₽)</Label>
              <Input
                type="number"
                inputMode="decimal"
                placeholder="0"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                className="h-10"
              />
            </div>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={handleAdd} disabled={setLimit.isPending}>
                Сохранить
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>
                Отмена
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Limits list */}
      {loadingLimits ? (
        <div className="space-y-3">
          {Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      ) : !limits?.length ? (
        <div className="text-center py-16 px-4 bg-muted/30 rounded-xl border border-dashed">
          <p className="text-sm font-medium mb-1">Нет лимитов</p>
          <p className="text-xs text-muted-foreground">Нажмите «Добавить» чтобы установить лимит на категорию</p>
        </div>
      ) : (
        <div className="space-y-3">
          {limits.map(limit => {
            const spent = spentMap[limit.category] ?? 0;
            const pct = Math.min((spent / limit.monthly_limit) * 100, 100);
            const isOver = spent >= limit.monthly_limit;
            const isWarning = pct >= 80 && !isOver;

            return (
              <Card key={limit.id} className={`overflow-hidden ${isOver ? 'border-rose-300 dark:border-rose-700' : isWarning ? 'border-amber-300 dark:border-amber-700' : ''}`}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {(isOver || isWarning) && (
                        <AlertTriangle className={`w-4 h-4 flex-shrink-0 ${isOver ? 'text-rose-500' : 'text-amber-500'}`} />
                      )}
                      <p className="font-semibold text-sm truncate">{limit.category}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive flex-shrink-0"
                      onClick={() => handleDelete(limit.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Потрачено: <span className={`font-semibold ${isOver ? 'text-rose-600' : isWarning ? 'text-amber-600' : 'text-foreground'}`}>{formatCurrency(spent)}</span></span>
                      <span>Лимит: <span className="font-semibold text-foreground">{formatCurrency(limit.monthly_limit)}</span></span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${isOver ? 'bg-rose-500' : isWarning ? 'bg-amber-500' : 'bg-primary'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground text-right">
                      {isOver
                        ? `Превышение на ${formatCurrency(spent - limit.monthly_limit)}`
                        : `Осталось ${formatCurrency(limit.monthly_limit - spent)}`}
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
