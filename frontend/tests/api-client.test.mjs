import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { ApiError, apiRequest, uploadWithProgress } from "../src/lib/api/client.ts";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalXhr = globalThis.XMLHttpRequest;
const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.XMLHttpRequest = originalXhr;
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
  if (originalApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
  else process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
});

test("API requests use the same-origin proxy and preserve backend error details", async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  delete globalThis.window;
  let requestedUrl;
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify({ detail: "invalid upload" }), { status: 422 });
  };

  await assert.rejects(apiRequest("/api/v1/upload"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, "validation");
    assert.equal(error.status, 422);
    assert.equal(error.detail.detail, "invalid upload");
    return true;
  });
  assert.equal(requestedUrl, "/api/backend/api/v1/upload");
});

test("browser API base URL uses an explicitly configured local-development origin only on localhost", async () => {
  process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000/";
  globalThis.window = { location: { hostname: "localhost" } };
  let requestedUrl;
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return Response.json({ status: "OK" });
  };
  await apiRequest("/api/v1/health");
  assert.equal(requestedUrl, "/api/backend/api/v1/health");

  process.env.NEXT_PUBLIC_API_URL = "https://api.example.test";
  await apiRequest("/api/v1/health");
  assert.equal(requestedUrl, "https://api.example.test/api/v1/health");
});

test("upload XHR resolves valid JSON and rejects malformed error bodies without leaving the promise pending", async () => {
  const instances = [];
  class FakeXhr {
    upload = {};
    status = 422;
    responseText = "not-json";
    open(method, url) { this.method = method; this.url = url; }
    send(body) { this.body = body; instances.push(this); }
  }
  globalThis.XMLHttpRequest = FakeXhr;
  delete process.env.NEXT_PUBLIC_API_URL;
  delete globalThis.window;
  const form = new FormData();
  form.append("file", new Blob(["a,b\n1,2"]), "sample.csv");

  const failed = uploadWithProgress("/api/v1/upload", form);
  assert.equal(instances[0].method, "POST");
  assert.equal(instances[0].url, "/api/backend/api/v1/upload");
  assert.equal(instances[0].body, form);
  const failure = assert.rejects(failed, (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    return true;
  });
  instances[0].onload();
  await failure;

  const successful = uploadWithProgress("/api/v1/upload", form);
  instances[1].status = 201;
  instances[1].responseText = JSON.stringify({ upload_id: "upload-1" });
  const result = successful.then((value) => value);
  instances[1].onload();
  assert.deepEqual(await result, { upload_id: "upload-1" });

  const timedOut = uploadWithProgress("/api/v1/upload", form);
  assert.equal(instances[2].timeout, 120_000);
  const timeoutFailure = assert.rejects(timedOut, (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, "network");
    return true;
  });
  instances[2].ontimeout();
  await timeoutFailure;
});
