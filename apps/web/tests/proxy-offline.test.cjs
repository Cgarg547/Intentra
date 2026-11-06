/* eslint-disable @typescript-eslint/no-require-imports -- CommonJS is needed to replace the proxy dependency in require.cache. */
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const ts = require('typescript');

// Exercise the installed rewrite proxy without opening sockets or starting Next.
const { proxyRequest } = require('next/dist/server/lib/router-utils/proxy-request');
const httpxyPath = require.resolve('next/dist/compiled/httpxy');

async function runProxy(timeout, failure = false) {
  const original = require.cache[httpxyPath];
  let options;
  class FakeProxy extends EventEmitter {
    constructor(value) { super(); options = value; }
    async web(req, res) {
      if (failure) throw Object.assign(new Error('simulated reset'), { code: 'ECONNRESET' });
      const outgoing = new EventEmitter();
      outgoing.destroy = () => {};
      this.emit('proxyReq', outgoing);
      // A completed upstream HTTP response is forwarded with its status.
      res.statusCode = 503;
      res.end('{"detail":"provider unavailable"}');
      outgoing.emit('close');
    }
    close() {}
  }
  require.cache[httpxyPath] = { exports: { ProxyServer: FakeProxy } };
  const req = { headers: { host: 'localhost:3000' } };
  const res = new EventEmitter();
  res.end = (body) => { res.body = body; };
  try {
    const pending = proxyRequest(req, res, {
      protocol: 'http:', hostname: '127.0.0.1', port: '8000', pathname: '/api/agents/proposals', query: {},
    }, undefined, undefined, timeout);
    if (failure) await assert.rejects(pending, { code: 'ECONNRESET' });
    else await pending;
    return { options, res };
  } finally {
    require.cache[httpxyPath] = original;
  }
}

test('rewrite proxy defaults to 30 seconds and turns transport failure into 500', async () => {
  const { mock } = require('node:test');
  const log = mock.method(console, 'error', () => {});
  try {
    const { options, res } = await runProxy(undefined, true);
    assert.equal(options.proxyTimeout, 30_000);
    assert.equal(res.statusCode, 500);
  } finally { log.mock.restore(); }
});

test('configured rewrite deadline accommodates maximum Ollama deadline and forwards 503', async () => {
  const source = readFileSync(require.resolve('../next.config.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const configModule = { exports: {} };
  new Function('module', 'exports', 'require', compiled.outputText)(configModule, configModule.exports, require);
  const config = configModule.exports.default;
  const { options, res } = await runProxy(config.experimental?.proxyTimeout);
  assert.ok(options.proxyTimeout > 300_000, 'proxy must outlast the maximum 300s provider deadline');
  assert.equal(res.statusCode, 503);
});
