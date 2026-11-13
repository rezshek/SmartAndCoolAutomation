import assert from "node:assert/strict";
import test from "node:test";
import { isLocalRequest } from "../lib/local-access.ts";

test("accepts same-origin browser requests on both loopback names", () => {
  for (const host of ["127.0.0.1:3000", "localhost:3000", "[::1]:3001"]) {
    assert.equal(
      isLocalRequest(new Headers({ host, origin: `http://${host}` })),
      true,
    );
  }
});
test("rejects public hosts, mismatched origins, cross-site requests and invalid authority", () => {
  for (const values of [
    { host: "admin.example:3000", origin: "http://admin.example:3000" },
    { host: "127.0.0.1:3000", origin: "https://evil.example" },
    { host: "127.0.0.1:3000", origin: "http://localhost:3000" },
    { host: "localhost:3000", "sec-fetch-site": "cross-site" },
    { host: "localhost:8080" },
    { host: "localhost:3000/extra" },
    { host: "user@localhost:3000" },
    {},
  ])
    assert.equal(isLocalRequest(new Headers(values)), false);
});
