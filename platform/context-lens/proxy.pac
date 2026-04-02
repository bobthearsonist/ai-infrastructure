// PAC file for routing LLM API traffic through mitmproxy.
// Routes GitHub Copilot and Anthropic (Claude Code) traffic; everything else goes direct.
//
// Usage in VS Code settings.json:
//   "http.proxyAutoconfigUrl": "file:///C:/Users/YourName/.context-lens/proxy.pac"
//   "http.proxyStrictSSL": false
//
// Requires mitmproxy CA cert installed in OS trust store:
//   certutil -addstore Root "%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer"

function FindProxyForURL(url, host) {
    if (dnsDomainIs(host, "githubcopilot.com") ||
        dnsDomainIs(host, "api.anthropic.com")) {
        return "PROXY 127.0.0.1:8080";
    }
    return "DIRECT";
}
