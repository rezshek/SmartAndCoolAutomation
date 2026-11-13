const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);

export function isLocalRequest(headers: Headers): boolean {
  try {
    // NextURL normalizes 127.0.0.1 to localhost. Compare the browser's Origin
    // with the validated incoming Host instead, preserving the actual authority.
    const authority = headers.get("host");
    if (!authority) return false;
    const target = new URL(`http://${authority}`);
    if (
      !loopbackHosts.has(target.hostname) ||
      !["3000", "3001"].includes(target.port) ||
      target.username ||
      target.password ||
      target.pathname !== "/"
    )
      return false;
    const origin = headers.get("origin");
    return (
      (!origin || origin === target.origin) &&
      headers.get("sec-fetch-site") !== "cross-site"
    );
  } catch {
    return false;
  }
}
