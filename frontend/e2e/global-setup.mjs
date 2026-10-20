import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const root = process.cwd();
const python = process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python";
const next = createRequire(import.meta.url).resolve("next/dist/bin/next");
const env = { ...process.env, NEXT_PUBLIC_API_URL: "http://127.0.0.1:18000", NEXT_TELEMETRY_DISABLED: "1" };
let backend;
let frontend;

function killTree(child) {
  if (!child?.pid) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    try { process.kill(-child.pid, "SIGKILL"); } catch {}
  }
}

async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

export default async function globalSetup() {
  backend = spawn(python, ["-B", "-X", "utf8", "../backend/scripts/run_e2e_backend.py"], {
    cwd: root, env, stdio: "ignore", detached: process.platform !== "win32",
  });
  await waitFor("http://127.0.0.1:18000/api/system/status", 30_000);
  const build = spawnSync(process.execPath, [next, "build"], { cwd: root, env, stdio: "ignore" });
  if (build.status !== 0) throw new Error(`Next build failed with exit code ${build.status}`);
  frontend = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "13000"], {
    cwd: root, env, stdio: "ignore", detached: process.platform !== "win32",
  });
  await waitFor("http://127.0.0.1:13000", 120_000);
  return async () => {
    killTree(frontend);
    killTree(backend);
  };
}
