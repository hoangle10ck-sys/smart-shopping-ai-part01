import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const next = createRequire(import.meta.url).resolve("next/dist/bin/next");
const env = { ...process.env, NEXT_PUBLIC_API_URL: "http://127.0.0.1:18000", NEXT_TELEMETRY_DISABLED: "1" };
// NEXT_PUBLIC variables are compiled into the bundle, so build with the test URL.
const build = spawnSync(process.execPath, [next, "build"], { env, stdio: "inherit" });
if (build.status !== 0) process.exit(build.status ?? 1);
const server = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "13000"], { env, stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.kill(signal));
server.on("exit", (code) => process.exit(code ?? 0));
