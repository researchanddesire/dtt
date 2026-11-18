#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { resolve } from "node:path";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  args.set(process.argv[index], process.argv[index + 1]);
}

const required = (name) => {
  const value = args.get(name);
  if (!value) throw new Error(`Missing ${name}`);
  return value;
};

const host = args.get("--host") ?? "0.0.0.0";
const port = Number(args.get("--port") ?? "8765");
const publicBase = required("--public-base").replace(/\/$/, "");
const bridgePath = resolve(required("--bridge"));
const v2Path = resolve(required("--v2"));
const bridgeBuild = required("--bridge-build");
const v2Build = required("--v2-build");
const version = args.get("--version") ?? "2.0.76";
const bridge = readFileSync(bridgePath);
const v2 = readFileSync(v2Path);
// Optional second legacy-layout application, offered in "legacy-update" mode
// so a device can be moved into its other OTA slot before it migrates.
const v1Path = args.get("--v1") ? resolve(args.get("--v1")) : null;
const v1 = v1Path ? readFileSync(v1Path) : null;
const v1Build = args.get("--v1-build") ?? "";
// Bootloader-region hashes the bridge accepts. With the gate on, a device
// that reports any other bootloader is not offered the bridge, as the
// dashboard resolver does.
const approvedBootloaders = new Set(
  (args.get("--approved-bootloaders") ?? "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean),
);
const digest = (content) => createHash("sha256").update(content).digest("hex");
const bridgeSha = digest(bridge);
const v2Sha = digest(v2);
const v1Sha = v1 ? digest(v1) : "";
const bucketPrefix =
  "/storage/v1/object/public/dtt-firmware/releases/lab";
// Artifacts may be served from another origin (for example HTTPS storage) by
// passing their full URLs; the bytes must match the local files.
const bridgeUrl =
  args.get("--bridge-url") ??
  `${publicBase}${bucketPrefix}/bridge/firmware.bin`;
const v2Url =
  args.get("--v2-url") ?? `${publicBase}${bucketPrefix}/v2/firmware.bin`;
const v1Url = `${publicBase}${bucketPrefix}/v1/firmware.bin`;
const events = [];
let mode = "hold";
let gate = false;

const record = (event) => {
  events.push({ at: new Date().toISOString(), ...event });
  if (events.length > 500) events.shift();
  process.stdout.write(`${JSON.stringify(events.at(-1))}\n`);
};

const sendJson = (response, status, value) => {
  const body = Buffer.from(JSON.stringify(value));
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Length": body.length,
    "Content-Type": "application/json",
  });
  response.end(body);
};

const noUpdate = (report, reason = "updates-disabled") => ({
  protocolVersion: 1,
  shouldUpdate: false,
  updateAvailable: false,
  reason,
  reportedTrack: report.reportedTrack,
  assignedTrack: report.reportedTrack,
  trackChanged: false,
  currentVersion: report.currentVersion,
  detectedHardwareVariant: "v2",
  selectedHardwareVariant: "v2",
  targetVersion: reason === "already-current" ? version : null,
  nextHopVersion: null,
  update: null,
  nextCheckSeconds: 60,
});

const update = ({
  report,
  kind,
  buildSha,
  artifactUrl,
  artifactSha,
  artifactSize,
  releaseId,
}) => ({
  protocolVersion: 1,
  shouldUpdate: true,
  updateAvailable: true,
  reason: "update-available",
  reportedTrack: report.reportedTrack,
  assignedTrack: report.reportedTrack,
  trackChanged: false,
  currentVersion: report.currentVersion,
  detectedHardwareVariant: "v2",
  selectedHardwareVariant: "v2",
  targetVersion: version,
  nextHopVersion: version,
  update: {
    releaseId,
    kind,
    buildSha,
    publishedAt: "2026-07-31T00:00:00.000Z",
    artifacts: [
      {
        role: "application",
        url: artifactUrl,
        sha256: artifactSha,
        sizeBytes: artifactSize,
        installOrder: 0,
      },
    ],
  },
  nextCheckSeconds: 60,
});

const readJson = async (request) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
};

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", publicBase);
  try {
    if (request.method === "POST" && url.pathname === "/__lab/control") {
      const body = await readJson(request);
      const allowed = new Set([
        "hold",
        "legacy-update",
        "corrupt-migration",
        "corrupt-final",
        "pause-final",
        "migrate",
        "unreachable",
      ]);
      if (body.mode !== undefined && !allowed.has(body.mode)) {
        return sendJson(response, 400, { error: "invalid mode" });
      }
      if (body.mode === "legacy-update" && !v1) {
        return sendJson(response, 400, { error: "no --v1 image" });
      }
      if (body.gate !== undefined && typeof body.gate !== "boolean") {
        return sendJson(response, 400, { error: "invalid gate" });
      }
      mode = body.mode ?? mode;
      gate = body.gate ?? gate;
      record({ type: "control", mode, gate });
      return sendJson(response, 200, { mode, gate });
    }

    if (request.method === "GET" && url.pathname === "/__lab/events") {
      return sendJson(response, 200, { mode, gate, events });
    }

    if (mode === "unreachable") {
      // Looks like an outage to the device: the connection drops unanswered.
      record({ type: "dropped", path: url.pathname });
      request.socket.destroy();
      return;
    }

    if (
      request.method === "POST" &&
      url.pathname === "/api/firmware/v1/check"
    ) {
      const report = await readJson(request);
      record({
        type: "check",
        mode,
        report: {
          // Enough to tell devices apart without logging their identity.
          deviceIdDigest: digest(String(report.deviceId ?? "")).slice(0, 12),
          currentBuild: report.currentBuild,
          currentVersion: report.currentVersion,
          flashSizeBytes: report.flashSizeBytes,
          otaSlotSizeBytes: report.otaSlotSizeBytes,
          partitionLayout: report.partitionLayout,
          partitionTableHash: report.partitionTableHash,
          bootloaderHash: report.bootloaderHash,
        },
      });
      if (mode === "hold") {
        return sendJson(response, 200, noUpdate(report));
      }
      if (mode === "legacy-update") {
        if (
          report.partitionLayout !== "legacy-v1" ||
          report.currentBuild === v1Build
        ) {
          return sendJson(response, 200, noUpdate(report, "already-current"));
        }
        return sendJson(response, 200, {
          ...update({
            report,
            kind: "firmware",
            buildSha: v1Build,
            artifactUrl: v1Url,
            artifactSha: v1Sha,
            artifactSize: v1.length,
            releaseId: "00000000-0000-4000-8000-000000000003",
          }),
          detectedHardwareVariant: "v2",
          selectedHardwareVariant: "v1",
        });
      }
      if (report.partitionLayout === "legacy-v1") {
        if (
          gate &&
          !approvedBootloaders.has(
            String(report.bootloaderHash ?? "").toLowerCase(),
          )
        ) {
          record({ type: "migration-withheld", reason: "bootloader" });
          return sendJson(
            response,
            200,
            noUpdate(report, "incompatible-device"),
          );
        }
        const migration = update({
          report,
          kind: "migration",
          buildSha: bridgeBuild,
          artifactUrl: bridgeUrl,
          artifactSha:
            mode === "corrupt-migration" ? "0".repeat(64) : bridgeSha,
          artifactSize: bridge.length,
          releaseId: "00000000-0000-4000-8000-000000000001",
        });
        return sendJson(response, 200, migration);
      }
      if (report.partitionLayout === "dtt-ota-16mb-v1") {
        if (mode === "pause-final") {
          record({ type: "final-paused" });
          return sendJson(response, 503, { error: "lab final paused" });
        }
        if (
          report.currentBuild &&
          (report.currentBuild === v2Build ||
            v2Build.startsWith(report.currentBuild) ||
            report.currentBuild.startsWith(v2Build))
        ) {
          return sendJson(response, 200, noUpdate(report, "already-current"));
        }
        return sendJson(
          response,
          200,
          update({
            report,
            kind: "firmware",
            buildSha: v2Build,
            artifactUrl: v2Url,
            artifactSha: mode === "corrupt-final" ? "0".repeat(64) : v2Sha,
            artifactSize: v2.length,
            releaseId: "00000000-0000-4000-8000-000000000002",
          }),
        );
      }
      return sendJson(response, 200, noUpdate(report, "incompatible-device"));
    }

    if (
      request.method === "POST" &&
      url.pathname.startsWith("/api/dtt/v2/")
    ) {
      await readJson(request);
      return sendJson(response, 200, {});
    }

    const artifact =
      url.pathname === `${bucketPrefix}/bridge/firmware.bin`
        ? bridge
        : url.pathname === `${bucketPrefix}/v2/firmware.bin`
          ? v2
          : url.pathname === `${bucketPrefix}/v1/firmware.bin`
            ? v1
            : null;
    if (request.method === "GET" && artifact) {
      record({ type: "artifact", path: url.pathname, bytes: artifact.length });
      response.writeHead(200, {
        "Cache-Control": "no-store",
        "Content-Length": artifact.length,
        "Content-Type": "application/octet-stream",
      });
      return response.end(artifact);
    }

    return sendJson(response, 404, { error: "not found" });
  } catch (error) {
    record({ type: "server-error", message: String(error) });
    return sendJson(response, 500, { error: String(error) });
  }
});

server.listen(port, host, () => {
  process.stdout.write(
    `${JSON.stringify({
      type: "ready",
      host,
      port,
      publicBase,
      mode,
      bridge: {
        path: bridgePath,
        size: statSync(bridgePath).size,
        sha256: bridgeSha,
        build: bridgeBuild,
      },
      v2: {
        path: v2Path,
        size: statSync(v2Path).size,
        sha256: v2Sha,
        build: v2Build,
      },
    })}\n`,
  );
});
