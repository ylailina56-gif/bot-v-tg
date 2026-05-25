import { useState } from "react";
import { useLocation } from "wouter";
import { useUser } from "@/App";
import { useCreateTransaction, getGetBalanceQueryKey, getGetMonthlySummaryQueryKey, getListTransactionsQueryKey, getGetCategorySummaryQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowDownIcon, ArrowUpIcon, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function AddTransaction() {
  const [, setLocation] = useLocation();
  const { userId } = useUser();
  const queryClient = useQueryClient();
  const createTx = useCreateTransaction();
  const { toast } = useToast();

  const [type, setType] = useState<"expense" | "income">("expense");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [note, setNote] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
      toast({ title: "Invalid amount", variant: "destructive" });
      return;
    }
    if (!category.trim()) {
      toast({ title: "Category required", variant: "destructive" });
      return;
    }

    createTx.mutate(
      {
        data: {
          user_id: userId,
          type,
          amount: Number(amount),
          category: category.trim(),
          note: note.trim() || undefined,
        }
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getGetBalanceQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getGetMonthlySummaryQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getListTransactionsQueryKey({ user_id: userId }) });
          queryClient.invalidateQueries({ queryKey: getGetCategorySummaryQueryKey({ user_id: userId }) });
          
          toast({ title: "Transaction added successfully" });
          setLocation("/");
        },
        onError: () => {
          toast({ title: "Failed to add transaction", variant: "destructive" });
        }
      }
    );
  };

  return (
    <div className="p-4 space-y-6">
      <header className="py-2">
        <h1 className="text-xl font-bold tracking-tight">Add Transaction</h1>
        <p className="text-sm text-muted-foreground">Record a new income or expense</p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Type Toggle */}
        <div className="flex p-1 bg-muted/50 rounded-xl border">
          <button
            type="button"
            onClick={() => setType("expense")}
            className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-all ${
              type === "expense" 
                ? "bg-background text-foreground shadow-sm" 
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <ArrowUpIcon className={`w-4 h-4 ${type === 'expense' ? 'text-rose-500' : ''}`} />
            Expense
          </button>
          <button
            type="button"
            onClick={() => setType("income")}
            className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-all ${
              type === "income" 
                ? "bg-background text-foreground shadow-sm" 
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <ArrowDownIcon className={`w-4 h-4 ${type === 'income' ? 'text-emerald-500' : ''}`} />
            Income
          </button>
        </div>

        <Card className="border-none shadow-sm bg-card">
          <CardContent className="p-5 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="amount" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Amount</Label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground font-semibold">
                  ₽
                </span>
                <Input
                  id="amount"
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="pl-8 text-2xl font-bold h-14"
                  autoFocus
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="category" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Category</Label>
              <Input
                id="category"
                type="text"
                placeholder={type === 'expense' ? 'e.g. Groceries, Transport' : 'e.g. Salary, Freelance'}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="h-12"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="note" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Note (Optional)</Label>
              <Input
                id="note"
                type="text"
                placeholder="Details about this transaction"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="h-12"
              />
            </div>
          </CardContent>
        </Card>

        <Button 
          type="submit" 
          className="w-full h-14 text-base font-semibold rounded-xl"
          disabled={createTx.isPending}
        >
          {createTx.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
          ) : null}
          Save Transaction
        </Button>
      </form>
    </div>
  );
}
