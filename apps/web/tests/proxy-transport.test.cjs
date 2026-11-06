/* eslint-disable @typescript-eslint/no-require-imports -- Exercise Next's installed CommonJS proxy entry point. */
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const ts = require('typescript');
const { proxyRequest } = require('next/dist/server/lib/router-utils/proxy-request');

const safeBody = JSON.stringify({ detail: 'Synthetic provider unavailable. Request was not evaluated.' });
const forbiddenPorts = new Set([3000, 8000, 5433, 11434]);

function configuredTimeout() {
  const source = readFileSync(require.resolve('../next.config.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const configModule = { exports: {} };
  new Function('module', 'exports', 'require', compiled.outputText)(configModule, configModule.exports, require);
  return configModule.exports.default.experimental.proxyTimeout;
}

async function bounded(promise, ms = 3000) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Synthetic harness deadline exceeded')), ms);
    })]);
  } finally { clearTimeout(timer); }
}

async function listen(t, handler) {
  const server = http.createServer(handler);
  const sockets = new Set();
  server.on('connection', (socket) => {
    sockets.add(socket);
    socket.once('close', () => sockets.delete(socket));
  });
  t.after(async () => {
    for (const socket of sockets) socket.destroy();
    if (server.listening) await new Promise((resolve) => server.close(resolve));
  });
  // Port zero asks the OS for an unused ephemeral port; no existing service is used.
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  assert.ok(!forbiddenPorts.has(server.address().port));
  return server;
}

async function harness(t, handler, timeout = configuredTimeout()) {
  const upstream = await listen(t, handler);
  const errors = [];
  const pending = new Set();
  // Next logs expected proxy resets; keep synthetic diagnostics inside the test.
  t.mock.method(console, 'error', () => {});
  const proxy = await listen(t, (req, res) => {
    const task = proxyRequest(req, res, {
      protocol: 'http:', hostname: '127.0.0.1', port: String(upstream.address().port),
      pathname: '/synthetic', query: {},
    }, undefined, undefined, timeout).catch((error) => { errors.push(error.code); });
    pending.add(task);
    task.finally(() => pending.delete(task));
  });
  const port = proxy.address().port;
  function request() {
    let outgoing;
    const result = new Promise((resolve, reject) => {
      outgoing = http.get({ hostname: '127.0.0.1', port, path: '/synthetic', agent: false }, (res) => {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('error', reject);
        res.on('end', () => resolve({ status: res.statusCode, headers: res.headers,
          body: Buffer.concat(chunks).toString('utf8') }));
      });
      outgoing.on('error', reject);
    });
    t.after(() => outgoing.destroy());
    return { outgoing, result };
  }
  return { request, errors, pending };
}

function respondUnavailable(res) {
  res.writeHead(503, { 'Content-Type': 'application/json' });
  res.end(safeBody);
}

test('real proxy forwards an upstream sanitized 503 body and content type', { timeout: 5000 }, async (t) => {
  const proxy = await harness(t, (_req, res) => respondUnavailable(res));
  const response = await bounded(proxy.request().result);
  assert.equal(response.status, 503);
  assert.equal(response.body, safeBody);
  assert.equal(response.headers['content-type'], 'application/json');
  assert.deepEqual(proxy.errors, []);
});

test('configured real proxy allows a silent response beyond the old 30s limit', { timeout: 40000 }, async (t) => {
  assert.equal(configuredTimeout(), 330_000);
  const proxy = await harness(t, (_req, res) => {
    const timer = setTimeout(() => respondUnavailable(res), 31_250);
    res.once('close', () => clearTimeout(timer));
  });
  const start = performance.now();
  const response = await bounded(proxy.request().result, 38_000);
  assert.ok(performance.now() - start > 30_000);
  assert.equal(response.status, 503);
  assert.equal(response.body, safeBody);
  assert.deepEqual(proxy.errors, []);
});

test('real proxy expires an idle upstream and closes its connection', { timeout: 5000 }, async (t) => {
  let closed;
  const upstreamClosed = new Promise((resolve) => { closed = resolve; });
  const proxy = await harness(t, (_req, res) => res.once('close', closed), 100);
  const response = await bounded(proxy.request().result);
  assert.equal(response.status, 500);
  assert.equal(response.body, 'Internal Server Error');
  await bounded(upstreamClosed);
  await bounded(Promise.all([...proxy.pending]));
  assert.deepEqual(proxy.errors, ['ECONNRESET']);
});

test('real proxy sanitizes an upstream connection reset', { timeout: 5000 }, async (t) => {
  const proxy = await harness(t, (req) => req.socket.destroy());
  const response = await bounded(proxy.request().result);
  assert.equal(response.status, 500);
  assert.equal(response.body, 'Internal Server Error');
  await bounded(Promise.all([...proxy.pending]));
  assert.deepEqual(proxy.errors, ['ECONNRESET']);
});

test('downstream disconnect closes the real upstream request and settles proxy work', { timeout: 5000 }, async (t) => {
  let accepted;
  let closed;
  const upstreamAccepted = new Promise((resolve) => { accepted = resolve; });
  const upstreamClosed = new Promise((resolve) => { closed = resolve; });
  const proxy = await harness(t, (_req, res) => {
    res.once('close', closed);
    accepted();
  });
  const client = proxy.request();
  const clientResult = client.result.catch((error) => error.code);
  await bounded(upstreamAccepted);
  client.outgoing.destroy();
  assert.equal(await bounded(clientResult), 'ECONNRESET');
  await bounded(upstreamClosed);
  await bounded(Promise.all([...proxy.pending]));
  assert.equal(proxy.pending.size, 0);
});
