import { NextResponse } from "next/server";
import { loadStockDetail } from "@/lib/report/loaders";

type RouteContext = {
  params: Promise<{
    symbol: string;
  }>;
};

export async function GET(_: Request, context: RouteContext) {
  try {
    const { symbol } = await context.params;
    return NextResponse.json(loadStockDetail(symbol), {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Error reading stock detail:", error);
    return NextResponse.json({ error: "Stock detail not found" }, { status: 404 });
  }
}
