import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type MetricCardProps = {
  title: string;
  value: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
};

export function MetricCard({ title, value, description, icon }: MetricCardProps) {
  return (
    <Card className="border-slate-800 bg-slate-900/80">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-slate-400">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-slate-100">{value}</div>
        {description ? <p className="mt-2 text-xs text-slate-400">{description}</p> : null}
      </CardContent>
    </Card>
  );
}
