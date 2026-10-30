import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { createServer } from "node:net";

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

async function assertPortAvailable(port) {
  await new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", () => reject(new Error(
      `E2E port ${port} is already in use; refusing to reuse an existing server or database.`
    )));
    server.listen({ host: "127.0.0.1", port, exclusive: true }, () => {
      server.close(error => error ? reject(error) : resolve());
    });
  });
}

async function waitFor(url, timeoutMs, child) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`E2E server exited before becoming ready: ${url}`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

export default async function globalSetup() {
  try {
    await assertPortAvailable(18000);
    await assertPortAvailable(13000);
    backend = spawn(python, ["-B", "-X", "utf8", "../backend/scripts/run_e2e_backend.py"], {
      cwd: root, env, stdio: "ignore", detached: process.platform !== "win32",
    });
    await waitFor("http://127.0.0.1:18000/api/system/status", 30_000, backend);
    const build = spawnSync(process.execPath, [next, "build"], { cwd: root, env, stdio: "ignore" });
    if (build.status !== 0) throw new Error(`Next build failed with exit code ${build.status}`);
    frontend = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "13000"], {
      cwd: root, env, stdio: "ignore", detached: process.platform !== "win32",
    });
    await waitFor("http://127.0.0.1:13000", 120_000, frontend);
    return async () => {
      killTree(frontend);
      killTree(backend);
    };
  } catch (error) {
    killTree(frontend);
    killTree(backend);
    throw error;
  }
}
