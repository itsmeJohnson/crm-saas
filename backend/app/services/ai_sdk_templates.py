"""Official client SDKs for the public AI API, generated as source you can drop
straight into a project.

Every SDK speaks the same contract — API-key auth, versioned paths, 429-aware
retries, SSE streaming and HMAC webhook verification — and none of them names a
model provider: routing stays server-side in the AI gateway, so an org can move
between OpenAI / Azure / Anthropic / Gemini / Ollama / custom without the client
changing a line.
"""

SDK_LANGUAGES: dict[str, dict] = {
    "python": {"label": "Python", "filename": "crm_ai.py", "language": "python",
               "install": "pip install requests", "min_version": "3.9"},
    "node": {"label": "Node.js", "filename": "crm-ai.js", "language": "javascript",
             "install": "no dependencies (Node 18+ global fetch)", "min_version": "18"},
    "java": {"label": "Java", "filename": "CrmAiClient.java", "language": "java",
             "install": "no dependencies (java.net.http)", "min_version": "11"},
}


# --------------------------------------------------------------------------- #
#  Python
# --------------------------------------------------------------------------- #
def _python_sdk(base_url: str, version: str) -> str:
    return f'''"""CRM AI API — official Python client (v{version}).

    pip install requests

    from crm_ai import CRMAIClient
    client = CRMAIClient(api_key="crm_live_...")
    print(client.generate("Summarise this lead in 3 bullets")["text"])

Provider-agnostic by design: pass provider/model only when you want to pin a
route, otherwise the server's configured fallback chain decides.
"""
import hashlib
import hmac
import json
import time
from typing import Any, Iterator

import requests

BASE_URL = "{base_url}"
API_VERSION = "{version}"


class CRMAIError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"[{{status_code}}] {{detail}}")
        self.status_code = status_code
        self.detail = detail


class CRMAIRateLimitError(CRMAIError):
    def __init__(self, detail: str, retry_after: int = 1):
        super().__init__(429, detail)
        self.retry_after = retry_after


class CRMAIClient:
    """Thin, dependency-light client for the CRM AI API."""

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: float = 60.0,
                 max_retries: int = 3):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    # ---- transport -------------------------------------------------------
    def _headers(self) -> dict:
        return {{"Authorization": f"Bearer {{self.api_key}}",
                "X-API-Version": API_VERSION,
                "Content-Type": "application/json",
                "User-Agent": f"crm-ai-python/{{API_VERSION}}"}}

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{{self.base_url}}{{path}}"
        attempt = 0
        while True:
            attempt += 1
            resp = self.session.request(method, url, headers=self._headers(),
                                        timeout=self.timeout, **kwargs)
            if resp.status_code == 429 and attempt <= self.max_retries:
                time.sleep(float(resp.headers.get("Retry-After", "1")))
                continue
            if resp.status_code >= 400:
                detail = self._detail(resp)
                if resp.status_code == 429:
                    raise CRMAIRateLimitError(detail, int(resp.headers.get("Retry-After", "1")))
                raise CRMAIError(resp.status_code, detail)
            return resp.json()

    @staticmethod
    def _detail(resp) -> str:
        try:
            return resp.json().get("detail") or resp.text
        except Exception:
            return resp.text

    # ---- endpoints -------------------------------------------------------
    def generate(self, prompt: str | None = None, *, messages: list | None = None,
                 task_type: str = "general", template_key: str | None = None,
                 variables: dict | None = None, provider: str | None = None,
                 model: str | None = None, temperature: float | None = None,
                 max_tokens: int | None = None) -> dict:
        """One-shot completion. Returns {{text, provider, model, tokens, cost_usd, ...}}."""
        body = {{"prompt": prompt, "messages": messages, "task_type": task_type,
                "template_key": template_key, "variables": variables,
                "provider": provider, "model": model, "temperature": temperature,
                "max_tokens": max_tokens}}
        return self._request("POST", "/generate", json={{k: v for k, v in body.items() if v is not None}})

    def chat(self, message: str, conversation_id: str | None = None, **kwargs) -> dict:
        """Multi-turn chat with server-side conversation memory."""
        body = {{"message": message, "conversation_id": conversation_id, **kwargs}}
        return self._request("POST", "/chat", json={{k: v for k, v in body.items() if v is not None}})

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Server-sent-events streaming. Yields text deltas as they arrive."""
        body = {{"prompt": prompt, **{{k: v for k, v in kwargs.items() if v is not None}}}}
        with self.session.post(f"{{self.base_url}}/stream", headers=self._headers(),
                               json=body, stream=True, timeout=self.timeout) as resp:
            if resp.status_code >= 400:
                raise CRMAIError(resp.status_code, self._detail(resp))
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk).get("delta")
                except json.JSONDecodeError:
                    continue
                if delta:
                    yield delta

    def models(self) -> dict:
        """Providers and models this key may route to."""
        return self._request("GET", "/models")

    def templates(self) -> list:
        """Approved prompt templates callable via template_key."""
        return self._request("GET", "/templates")

    def usage(self, days: int = 30) -> dict:
        """This key's request/token/cost usage and remaining quota."""
        return self._request("GET", f"/usage?days={{days}}")

    def version(self) -> dict:
        return self._request("GET", "/version")


def verify_webhook(secret: str, signature_header: str, raw_body: bytes,
                   tolerance_seconds: int = 300) -> bool:
    """Verify an X-CRM-AI-Signature header: 't=<unix>,v1=<hex hmac-sha256>'.

    The signed payload is "<timestamp>.<raw body>". Timestamps outside the
    tolerance window are rejected to blunt replay attacks.
    """
    parts = dict(p.split("=", 1) for p in (signature_header or "").split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("v1")
    if not ts or not sig:
        return False
    if abs(time.time() - int(ts)) > tolerance_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{{ts}}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
'''


# --------------------------------------------------------------------------- #
#  Node.js
# --------------------------------------------------------------------------- #
def _node_sdk(base_url: str, version: str) -> str:
    return f'''/**
 * CRM AI API — official Node.js client (v{version}).
 * Node 18+ (global fetch). No dependencies.
 *
 *   const {{ CRMAIClient }} = require('./crm-ai');
 *   const client = new CRMAIClient({{ apiKey: 'crm_live_...' }});
 *   const res = await client.generate('Summarise this lead in 3 bullets');
 *
 * Provider-agnostic: omit provider/model to use the server's fallback chain.
 */
const crypto = require('crypto');

const BASE_URL = '{base_url}';
const API_VERSION = '{version}';

class CRMAIError extends Error {{
  constructor(statusCode, detail) {{
    super(`[${{statusCode}}] ${{detail}}`);
    this.name = 'CRMAIError';
    this.statusCode = statusCode;
    this.detail = detail;
  }}
}}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CRMAIClient {{
  constructor({{ apiKey, baseUrl = BASE_URL, timeout = 60000, maxRetries = 3 }} = {{}}) {{
    if (!apiKey) throw new Error('apiKey is required');
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\\/$/, '');
    this.timeout = timeout;
    this.maxRetries = maxRetries;
  }}

  _headers() {{
    return {{
      Authorization: `Bearer ${{this.apiKey}}`,
      'X-API-Version': API_VERSION,
      'Content-Type': 'application/json',
      'User-Agent': `crm-ai-node/${{API_VERSION}}`,
    }};
  }}

  async _request(method, path, body) {{
    const url = `${{this.baseUrl}}${{path}}`;
    for (let attempt = 1; ; attempt += 1) {{
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);
      let resp;
      try {{
        resp = await fetch(url, {{
          method,
          headers: this._headers(),
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        }});
      }} finally {{
        clearTimeout(timer);
      }}
      if (resp.status === 429 && attempt <= this.maxRetries) {{
        await sleep(Number(resp.headers.get('Retry-After') || 1) * 1000);
        continue;
      }}
      if (!resp.ok) {{
        let detail;
        try {{ detail = (await resp.json()).detail; }} catch {{ detail = await resp.text(); }}
        throw new CRMAIError(resp.status, detail);
      }}
      return resp.json();
    }}
  }}

  /** One-shot completion. */
  generate(prompt, opts = {{}}) {{
    return this._request('POST', '/generate', {{ prompt, ...opts }});
  }}

  /** Multi-turn chat with server-side conversation memory. */
  chat(message, opts = {{}}) {{
    return this._request('POST', '/chat', {{ message, ...opts }});
  }}

  /** SSE streaming — async iterator of text deltas. */
  async *stream(prompt, opts = {{}}) {{
    const resp = await fetch(`${{this.baseUrl}}/stream`, {{
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify({{ prompt, ...opts }}),
    }});
    if (!resp.ok) throw new CRMAIError(resp.status, await resp.text());
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {{
      const {{ done, value }} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {{ stream: true }});
      const lines = buffer.split('\\n');
      buffer = lines.pop();
      for (const line of lines) {{
        if (!line.startsWith('data: ')) continue;
        const chunk = line.slice(6);
        if (chunk === '[DONE]') return;
        try {{
          const {{ delta }} = JSON.parse(chunk);
          if (delta) yield delta;
        }} catch {{ /* keep reading */ }}
      }}
    }}
  }}

  models() {{ return this._request('GET', '/models'); }}
  templates() {{ return this._request('GET', '/templates'); }}
  usage(days = 30) {{ return this._request('GET', `/usage?days=${{days}}`); }}
  version() {{ return this._request('GET', '/version'); }}
}}

/**
 * Verify an X-CRM-AI-Signature header: 't=<unix>,v1=<hex hmac-sha256>'.
 * Signed payload is "<timestamp>.<raw body>".
 */
function verifyWebhook(secret, signatureHeader, rawBody, toleranceSeconds = 300) {{
  const parts = Object.fromEntries(
    String(signatureHeader || '').split(',').filter((p) => p.includes('=')).map((p) => {{
      const i = p.indexOf('=');
      return [p.slice(0, i), p.slice(i + 1)];
    }})
  );
  if (!parts.t || !parts.v1) return false;
  if (Math.abs(Date.now() / 1000 - Number(parts.t)) > toleranceSeconds) return false;
  const expected = crypto.createHmac('sha256', secret)
    .update(`${{parts.t}}.`).update(rawBody).digest('hex');
  const a = Buffer.from(expected);
  const b = Buffer.from(parts.v1);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}}

module.exports = {{ CRMAIClient, CRMAIError, verifyWebhook, BASE_URL, API_VERSION }};
'''


# --------------------------------------------------------------------------- #
#  Java
# --------------------------------------------------------------------------- #
def _java_sdk(base_url: str, version: str) -> str:
    return f'''/*
 * CRM AI API — official Java client (v{version}).
 * Java 11+ (java.net.http). No third-party dependencies.
 *
 *   CrmAiClient client = new CrmAiClient("crm_live_...");
 *   String json = client.generate("Summarise this lead in 3 bullets");
 *
 * Responses are returned as raw JSON strings so you can bind them with whatever
 * mapper your project already uses (Jackson, Gson, …).
 *
 * Provider-agnostic: leave provider/model null to use the server's fallback chain.
 */
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Consumer;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public class CrmAiClient {{

    public static final String BASE_URL = "{base_url}";
    public static final String API_VERSION = "{version}";

    public static class CrmAiException extends RuntimeException {{
        public final int statusCode;
        public CrmAiException(int statusCode, String detail) {{
            super("[" + statusCode + "] " + detail);
            this.statusCode = statusCode;
        }}
    }}

    private final String apiKey;
    private final String baseUrl;
    private final int maxRetries;
    private final HttpClient http;

    public CrmAiClient(String apiKey) {{ this(apiKey, BASE_URL, 60, 3); }}

    public CrmAiClient(String apiKey, String baseUrl, int timeoutSeconds, int maxRetries) {{
        if (apiKey == null || apiKey.isEmpty()) throw new IllegalArgumentException("apiKey is required");
        this.apiKey = apiKey;
        this.baseUrl = baseUrl.replaceAll("/$", "");
        this.maxRetries = maxRetries;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(timeoutSeconds)).build();
    }}

    private HttpRequest.Builder base(String path) {{
        return HttpRequest.newBuilder(URI.create(baseUrl + path))
                .header("Authorization", "Bearer " + apiKey)
                .header("X-API-Version", API_VERSION)
                .header("Content-Type", "application/json")
                .header("User-Agent", "crm-ai-java/" + API_VERSION);
    }}

    private String send(HttpRequest request) {{
        for (int attempt = 1; ; attempt++) {{
            HttpResponse<String> resp;
            try {{
                resp = http.send(request, HttpResponse.BodyHandlers.ofString());
            }} catch (IOException | InterruptedException e) {{
                throw new CrmAiException(0, e.getMessage());
            }}
            if (resp.statusCode() == 429 && attempt <= maxRetries) {{
                long wait = resp.headers().firstValue("Retry-After").map(Long::parseLong).orElse(1L);
                try {{ Thread.sleep(wait * 1000L); }} catch (InterruptedException ignored) {{ }}
                continue;
            }}
            if (resp.statusCode() >= 400) throw new CrmAiException(resp.statusCode(), resp.body());
            return resp.body();
        }}
    }}

    /** One-shot completion; returns the raw JSON response body. */
    public String generate(String prompt) {{
        return generate(prompt, null, null, "general");
    }}

    public String generate(String prompt, String provider, String model, String taskType) {{
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("prompt", prompt);
        body.put("task_type", taskType == null ? "general" : taskType);
        if (provider != null) body.put("provider", provider);
        if (model != null) body.put("model", model);
        return send(base("/generate").POST(HttpRequest.BodyPublishers.ofString(toJson(body))).build());
    }}

    /** Multi-turn chat with server-side conversation memory. */
    public String chat(String message, String conversationId) {{
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("message", message);
        if (conversationId != null) body.put("conversation_id", conversationId);
        return send(base("/chat").POST(HttpRequest.BodyPublishers.ofString(toJson(body))).build());
    }}

    /** SSE streaming: invokes the consumer once per text delta. */
    public void stream(String prompt, Consumer<String> onDelta) {{
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("prompt", prompt);
        HttpRequest req = base("/stream").POST(HttpRequest.BodyPublishers.ofString(toJson(body))).build();
        HttpResponse<java.util.stream.Stream<String>> resp;
        try {{
            resp = http.send(req, HttpResponse.BodyHandlers.ofLines());
        }} catch (IOException | InterruptedException e) {{
            throw new CrmAiException(0, e.getMessage());
        }}
        if (resp.statusCode() >= 400) throw new CrmAiException(resp.statusCode(), "stream failed");
        resp.body().forEach(line -> {{
            if (!line.startsWith("data: ")) return;
            String chunk = line.substring(6);
            if ("[DONE]".equals(chunk)) return;
            String delta = extractString(chunk, "delta");
            if (delta != null && !delta.isEmpty()) onDelta.accept(delta);
        }});
    }}

    public String models() {{ return send(base("/models").GET().build()); }}

    public String templates() {{ return send(base("/templates").GET().build()); }}

    public String usage(int days) {{ return send(base("/usage?days=" + days).GET().build()); }}

    public String version() {{ return send(base("/version").GET().build()); }}

    /**
     * Verify an X-CRM-AI-Signature header: "t=&lt;unix&gt;,v1=&lt;hex hmac-sha256&gt;".
     * Signed payload is "&lt;timestamp&gt;.&lt;raw body&gt;".
     */
    public static boolean verifyWebhook(String secret, String signatureHeader, String rawBody,
                                        long toleranceSeconds) {{
        if (signatureHeader == null) return false;
        String ts = null, sig = null;
        for (String part : signatureHeader.split(",")) {{
            int i = part.indexOf('=');
            if (i < 0) continue;
            String k = part.substring(0, i).trim();
            String v = part.substring(i + 1).trim();
            if (k.equals("t")) ts = v;
            if (k.equals("v1")) sig = v;
        }}
        if (ts == null || sig == null) return false;
        long now = System.currentTimeMillis() / 1000L;
        if (Math.abs(now - Long.parseLong(ts)) > toleranceSeconds) return false;
        try {{
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal((ts + "." + rawBody).getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte b : digest) hex.append(String.format("%02x", b));
            return java.security.MessageDigest.isEqual(
                    hex.toString().getBytes(StandardCharsets.UTF_8), sig.getBytes(StandardCharsets.UTF_8));
        }} catch (Exception e) {{
            return false;
        }}
    }}

    // ---- minimal JSON helpers (keeps the client dependency-free) ----
    private static String toJson(Map<String, Object> map) {{
        StringBuilder sb = new StringBuilder("{{");
        boolean first = true;
        for (Map.Entry<String, Object> e : map.entrySet()) {{
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(escape(e.getKey())).append("\\":");
            Object v = e.getValue();
            if (v == null) sb.append("null");
            else if (v instanceof Number || v instanceof Boolean) sb.append(v);
            else sb.append('"').append(escape(String.valueOf(v))).append('"');
        }}
        return sb.append('}}').toString();
    }}

    private static String escape(String s) {{
        return s.replace("\\\\", "\\\\\\\\").replace("\\"", "\\\\\\"")
                .replace("\\n", "\\\\n").replace("\\r", "\\\\r").replace("\\t", "\\\\t");
    }}

    private static String extractString(String json, String field) {{
        String needle = "\\"" + field + "\\":\\"";
        int i = json.indexOf(needle);
        if (i < 0) return null;
        int start = i + needle.length();
        StringBuilder out = new StringBuilder();
        for (int j = start; j < json.length(); j++) {{
            char c = json.charAt(j);
            if (c == '\\\\' && j + 1 < json.length()) {{
                char n = json.charAt(++j);
                switch (n) {{
                    case 'n': out.append('\\n'); break;
                    case 't': out.append('\\t'); break;
                    case 'r': out.append('\\r'); break;
                    default: out.append(n);
                }}
            }} else if (c == '"') {{
                break;
            }} else {{
                out.append(c);
            }}
        }}
        return out.toString();
    }}
}}
'''


_BUILDERS = {"python": _python_sdk, "node": _node_sdk, "java": _java_sdk}


def render_sdk(language: str, base_url: str, version: str) -> str:
    """Return the full source of the client SDK for `language`."""
    return _BUILDERS[language](base_url, version)


def render_examples(base_url: str, api_key_sample: str = "crm_live_xxxxxxxxxxxx") -> list[dict]:
    """Copy-paste examples per language for the core developer journeys."""
    return [
        {
            "key": "generate_curl", "title": "Generate a completion", "language": "bash",
            "code": (f'curl -X POST "{base_url}/generate" \\\n'
                     f'  -H "Authorization: Bearer {api_key_sample}" \\\n'
                     '  -H "Content-Type: application/json" \\\n'
                     '  -d \'{"prompt": "Summarise this lead in 3 bullets", "task_type": "general"}\''),
        },
        {
            "key": "generate_python", "title": "Generate a completion (Python)", "language": "python",
            "code": ('from crm_ai import CRMAIClient\n\n'
                     f'client = CRMAIClient(api_key="{api_key_sample}")\n'
                     'res = client.generate("Summarise this lead in 3 bullets")\n'
                     'print(res["text"], res["provider"], res["model"])'),
        },
        {
            "key": "stream_python", "title": "Stream a response (Python)", "language": "python",
            "code": ('for delta in client.stream("Draft a follow-up email"):\n'
                     '    print(delta, end="", flush=True)'),
        },
        {
            "key": "chat_node", "title": "Multi-turn chat (Node.js)", "language": "javascript",
            "code": ("const { CRMAIClient } = require('./crm-ai');\n\n"
                     f"const client = new CRMAIClient({{ apiKey: '{api_key_sample}' }});\n"
                     "const first = await client.chat('What changed on this account?');\n"
                     "const next = await client.chat('And the risks?', "
                     "{ conversation_id: first.conversation_id });"),
        },
        {
            "key": "stream_node", "title": "Stream a response (Node.js)", "language": "javascript",
            "code": ("for await (const delta of client.stream('Draft a follow-up email')) {\n"
                     "  process.stdout.write(delta);\n"
                     "}"),
        },
        {
            "key": "generate_java", "title": "Generate a completion (Java)", "language": "java",
            "code": (f'CrmAiClient client = new CrmAiClient("{api_key_sample}");\n'
                     'String json = client.generate("Summarise this lead in 3 bullets");\n'
                     'System.out.println(json);'),
        },
        {
            "key": "template", "title": "Call a prompt-studio template", "language": "bash",
            "code": (f'curl -X POST "{base_url}/generate" \\\n'
                     f'  -H "Authorization: Bearer {api_key_sample}" \\\n'
                     '  -H "Content-Type: application/json" \\\n'
                     '  -d \'{"template_key": "lead_summary", "variables": {"name": "Acme Corp"}}\''),
        },
        {
            "key": "webhook_python", "title": "Verify a webhook signature (Python)", "language": "python",
            "code": ('from crm_ai import verify_webhook\n\n'
                     '# Flask / FastAPI handler\n'
                     'sig = request.headers["X-CRM-AI-Signature"]\n'
                     'if not verify_webhook(WEBHOOK_SECRET, sig, request.get_data()):\n'
                     '    return "", 401'),
        },
        {
            "key": "rate_limit", "title": "Read rate-limit headers", "language": "bash",
            "code": ('# Every response carries the current budget:\n'
                     '#   X-RateLimit-Limit      requests allowed per minute\n'
                     '#   X-RateLimit-Remaining  requests left in this minute\n'
                     '#   X-RateLimit-Reset      unix seconds when the window resets\n'
                     '#   X-Quota-Remaining      requests left today\n'
                     '# On 429 a Retry-After header tells you how long to wait.\n'
                     f'curl -i -X POST "{base_url}/generate" '
                     f'-H "Authorization: Bearer {api_key_sample}" '
                     '-d \'{"prompt": "hi"}\' -H "Content-Type: application/json"'),
        },
    ]
