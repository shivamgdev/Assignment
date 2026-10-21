
const { spawn } = require("node:child_process");
const path = require("node:path");
const { after, before, beforeEach, test } = require("node:test");
const assert = require("node:assert/strict");

const PORT = 4317;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const serverPath = path.join(__dirname, "..", "mock-api.cjs");

let server;

async function resetApi() {
  const response = await fetch(`${BASE_URL}/api/reset`, { method: "POST" });
  assert.equal(response.status, 200);
  return response.json();
}

async function waitForApi() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (server.exitCode !== null) {
      throw new Error(`Mock API exited with code ${server.exitCode}`);
    }

    try {
      const response = await fetch(`${BASE_URL}/api/reset`, { method: "POST" });
      if (response.ok) return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  throw new Error("Mock API did not start within five seconds.");
}

before(async () => {
  server = spawn(process.execPath, [serverPath], {
    env: { ...process.env, PORT: String(PORT) },
    stdio: "inherit",
  });

  await waitForApi();
});

beforeEach(async () => {
  await resetApi();
});

after(() => {
  if (server && server.exitCode === null) {
    server.kill();
  }
});

test("search finds Sofia Rossi by applicant name", async () => {
  const response = await fetch(
    `${BASE_URL}/api/submissions?query=Sofia%20Rossi`,
  );
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.total, 1);
  assert.equal(body.items[0].id, "sub_1056");
  assert.equal(body.items[0].status, "NEEDS_REVIEW");
});

test("returning without a note is rejected", async () => {
  const response = await fetch(
    `${BASE_URL}/api/submissions/sub_1056/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: "RETURN", note: "" }),
    },
  );
  const body = await response.json();

  assert.equal(response.status, 422);
  assert.equal(body.error.code, "NOTE_REQUIRED");

  const detailResponse = await fetch(
    `${BASE_URL}/api/submissions/sub_1056`,
  );
  const detail = await detailResponse.json();

  assert.equal(detail.status, "NEEDS_REVIEW");
});

test("a successful approval removes the submission from the pending queue", async () => {
  const response = await fetch(
    `${BASE_URL}/api/submissions/sub_1050/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: "APPROVE", note: "" }),
    },
  );
  const detail = await response.json();

  assert.equal(response.status, 200);
  assert.equal(detail.status, "APPROVED");

  const queueResponse = await fetch(`${BASE_URL}/api/submissions`);
const queue = await queueResponse.json();

assert.equal(
  queue.items.some((item) => item.id === "sub_1050"),
  false,);
});

test("a transient decision failure can be retried successfully", async () => {
  const url = `${BASE_URL}/api/submissions/sub_1052/decision`;
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision: "APPROVE", note: "" }),
  };

  const firstResponse = await fetch(url, options);
  const firstBody = await firstResponse.json();

  assert.equal(firstResponse.status, 503);
  assert.equal(firstBody.error.code, "TEMPORARILY_UNAVAILABLE");

  const retryResponse = await fetch(url, options);
  const retryBody = await retryResponse.json();

  assert.equal(retryResponse.status, 200);
  assert.equal(retryBody.status, "APPROVED");
});

test("a concurrent reviewer conflict returns the latest recorded decision", async () => {
  const response = await fetch(
    `${BASE_URL}/api/submissions/sub_1056/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: "APPROVE", note: "" }),
    },
  );
  const body = await response.json();

  assert.equal(response.status, 409);
  assert.equal(body.error.code, "REVIEW_CONFLICT");
  assert.equal(body.submission.status, "APPROVED");
  assert.equal(
    body.submission.decision.reviewedBy,
    "Another operations reviewer",
  );
});
