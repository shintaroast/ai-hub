#!/usr/bin/env python3
"""ai-hub: Claude から他の AI (ChatGPT / Gemini / Grok / Hermes) に直接指示を出す CLI.

API キーはクラウド環境のネットワークシークレットとしてプロキシが自動で付与するため、
このスクリプトにキーを書く必要はありません（ローカル実行時は環境変数を使います）。

使い方:
  python3 ask.py chatgpt "プロンプト"
  python3 ask.py gemini  -f brief.md            # ファイルの内容をプロンプトに
  python3 ask.py all     "同じ質問を全員に"      # 並列で全 AI に送る
  python3 ask.py grok    -s "あなたはコピーライター" "キャッチコピーを5案"
  python3 ask.py models  openai                  # 使えるモデル一覧
  echo "..." | python3 ask.py hermes -           # 標準入力から
"""
import argparse, json, os, ssl, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))

def ctx():
    ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
    return ssl.create_default_context(cafile=ca) if os.path.exists(ca) else ssl.create_default_context()

def http(url, headers, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers},
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {url}: {e.read().decode(errors='replace')[:800]}")

def key(env):
    # クラウドではプロキシが本物のキーに差し替えるので、ダミー値で OK
    return os.environ.get(env) or "injected-by-proxy"

def openai_compat(p, prompt, system, model):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = http(p["base"] + "/chat/completions", {"Authorization": "Bearer " + key(p["key_env"])},
             {"model": model, "messages": msgs})
    return r["choices"][0]["message"]["content"]

def gemini(p, prompt, system, model):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = http(f"{p['base']}/models/{model}:generateContent", {"x-goog-api-key": key(p["key_env"])}, body)
    return "".join(part.get("text", "") for part in r["candidates"][0]["content"]["parts"])

def list_models(name):
    p = CFG["providers"][name]
    if p["kind"] == "gemini":
        r = http(p["base"] + "/models", {"x-goog-api-key": key(p["key_env"])})
        return [m["name"].split("/")[-1] for m in r.get("models", [])]
    r = http(p["base"] + "/models", {"Authorization": "Bearer " + key(p["key_env"])})
    return sorted(m["id"] for m in r.get("data", []))

def ask(name, prompt, system=None, model=None):
    alias = CFG["aliases"].get(name, name)
    p = CFG["providers"][alias]
    model = model or p["model"]
    fn = gemini if p["kind"] == "gemini" else openai_compat
    return fn(p, prompt, system, model)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="chatgpt | gemini | grok | hermes | all | models")
    ap.add_argument("prompt", nargs="?", default=None, help="プロンプト（- で標準入力）")
    ap.add_argument("-f", "--file", help="プロンプトをファイルから読む")
    ap.add_argument("-s", "--system", help="システムプロンプト（役割の指示）")
    ap.add_argument("-m", "--model", help="モデルを上書き")
    ap.add_argument("-o", "--out", help="結果を保存するディレクトリ")
    a = ap.parse_args()

    if a.target == "models":
        print("\n".join(list_models(CFG["aliases"].get(a.prompt, a.prompt))))
        return
    prompt = open(a.file, encoding="utf-8").read() if a.file else (sys.stdin.read() if a.prompt in (None, "-") else a.prompt)
    targets = CFG["all"] if a.target == "all" else [a.target]

    def run(t):
        try:
            return t, ask(t, prompt, a.system, None if a.target == "all" else a.model)
        except Exception as e:
            return t, f"[ERROR] {e}"

    with ThreadPoolExecutor(len(targets)) as ex:
        results = list(ex.map(run, targets))
    for t, text in results:
        print(f"\n===== {t} =====\n{text}")
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            open(os.path.join(a.out, f"{t}.md"), "w", encoding="utf-8").write(text)

if __name__ == "__main__":
    main()
