import { spawn } from "child_process";
import { NextResponse } from "next/server";
import { getRepoPaths, loadAnalysisStatus } from "@/lib/report/loaders";

function getPythonCommand() {
  return process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
}

export async function POST() {
  try {
    const status = loadAnalysisStatus();
    if (status.state === "running") {
      return NextResponse.json({
        triggered: false,
        reason: "analysis-already-running",
      });
    }

    const { repoRoot } = getRepoPaths();
    const child = spawn(
      getPythonCommand(),
      ["main.py", "--quiet", "--no-charts", "--no-html"],
      {
        cwd: repoRoot,
        detached: true,
        stdio: "ignore",
      },
    );

    child.unref();

    return NextResponse.json({
      triggered: true,
      pid: child.pid,
    });
  } catch (error) {
    console.error("Error triggering analysis refresh:", error);
    return NextResponse.json({ error: "Failed to trigger analysis refresh" }, { status: 500 });
  }
}
