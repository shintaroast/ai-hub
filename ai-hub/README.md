# ai-hub

Claude Code (claude.ai/code) から ChatGPT・Gemini・Grok・Hermes に直接指示を出すためのツール。
詳しい運用ルールは [CLAUDE.md](CLAUDE.md) を参照。

```bash
python3 ask.py all "新商品のキャッチコピーを3案ずつ" -o out/copy
```

依存ライブラリなし（Python 3 標準ライブラリのみ）。
ローカル PC で使う場合は `OPENAI_API_KEY` / `GEMINI_API_KEY` / `XAI_API_KEY` / `OPENROUTER_API_KEY` を環境変数に設定。
