import { NextResponse } from "next/server";
import { loadSilentAccumulation } from "@/lib/silent-accumulation/loaders";

export async function GET() {
  try {
    return NextResponse.json(await loadSilentAccumulation(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("Silent accumulation load error:", error);
    return NextResponse.json({ error: "Failed to load silent accumulation data" }, { status: 500 });
  }
}
