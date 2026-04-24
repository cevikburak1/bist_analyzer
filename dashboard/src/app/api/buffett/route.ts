import { NextResponse } from "next/server";
import { loadBuffettList } from "@/lib/buffett/loaders";

export async function GET() {
  try {
    return NextResponse.json(loadBuffettList(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("Buffett list error:", error);
    return NextResponse.json({ error: "Failed to load Buffett list" }, { status: 500 });
  }
}
