import { NextResponse } from "next/server";
import { loadAnalysisStatus } from "@/lib/report/loaders";

export async function GET() {
  try {
    return NextResponse.json(loadAnalysisStatus(), {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Error reading analysis status:", error);
    return NextResponse.json({ error: "Failed to read analysis status" }, { status: 500 });
  }
}
