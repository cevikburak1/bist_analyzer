import { NextResponse } from "next/server";
import { loadLatestReport } from "@/lib/report/loaders";

export async function GET() {
  try {
    return NextResponse.json(await loadLatestReport(), {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Error reading data:", error);
    return NextResponse.json({ error: "Failed to read data" }, { status: 500 });
  }
}
