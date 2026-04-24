import { NextResponse } from "next/server";
import { loadBuffettStock } from "@/lib/buffett/loaders";

type RouteContext = {
  params: Promise<{ symbol: string }>;
};

export async function GET(_: Request, context: RouteContext) {
  try {
    const { symbol } = await context.params;
    return NextResponse.json(loadBuffettStock(symbol), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("Buffett detail error:", error);
    return NextResponse.json({ error: "Buffett detail not found" }, { status: 404 });
  }
}
