# Pretty History for Claude Code

Claude Code履歴ビューアー - Claude Codeセッション履歴ファイルを様々なスタイルでフォーマット表示

## ⚠️ セキュリティに関する重要な注意事項

このツールはClaude Codeの会話履歴を読み取ります。以下の点にご注意ください：

- **機密情報の露出リスク**: 履歴ファイルには機密情報が含まれている可能性があります
- **アクセス制御**: 履歴ファイルへのアクセス権限を適切に管理してください
- **共有時の注意**: フォーマット済みの出力を共有する際は、機密情報が含まれていないか確認してください

## 免責事項

このツールは非公式のサードパーティ製ツールです。Anthropic社とは無関係であり、Claude CodeのUIを参考に作成されていますが、公式ツールではありません。

## 概要

JSON Lines (`.jsonl`) 形式の履歴ファイルを解析し、様々なスタイルで見やすく表示するツールです。デフォルトでは環境変数 `CLAUDE_HISTORY_DIR` で指定されたディレクトリ、または `~/.claude/projects/` を検索します。

## インストール

### PyPIから（推奨）

```bash
pip install claude-history-pretty
```

### ソースから（開発用）

```bash
git clone https://github.com/yourusername/pretty-history-claude-code.git
cd pretty-history-claude-code
pip install -e .
```

## 表示形式

### カラー表示（デフォルト）
Claude Code実行中と同じカラー表示を完全再現

```bash
claude-history  # デフォルトでカラー表示
```

### モノクロ表示
カラーなしでの表示

```bash
claude-history --no-color  # モノクロ表示
```

### 対話的ファイル選択（--select）
プロジェクトとファイルを対話的に選択

```bash
claude-history --select
```

**選択の流れ：**
1. プロジェクト一覧が表示される
2. プロジェクト番号を入力（0で全ファイル表示）
3. そのプロジェクト内のファイル一覧が表示される
4. ファイル番号を入力
5. 選択したファイルが整形表示される

## 環境設定

### 履歴ディレクトリの設定

デフォルトでは `~/.claude/projects/` を検索しますが、以下の方法で変更可能です：

```bash
# 環境変数で設定
export CLAUDE_HISTORY_DIR="/path/to/your/history/directory"

# コマンドラインオプションで指定
claude-history --base-dir /path/to/directory --select
```

### テーマ設定

4つの表示テーマから選択できます：

```bash
# 利用可能なテーマを表示
claude-history --list-themes

# テーマを指定して実行
claude-history --theme minimal    # シンプルなASCII表示
claude-history --theme default    # デフォルト（推奨）
claude-history --theme classic    # Unicode文字を使用
claude-history --theme plain      # プレーンテキスト
```

#### テーマプレビュー

**default** (デフォルト):
```
▶ Command
│  Result output
```

**minimal**:
```
- Command
  Result output
```

**classic**:
```
● Command
⎿  Result output
```

**plain**:
```
* Command
  Result output
```

## 使用方法

### インストール後の使用方法

```bash
# インストール実行
pip install -e .

# 対話的メニューモード（推奨）
claude-history --menu
# または引数なしで実行
claude-history

# 対話的ファイル選択のみ
claude-history --select

# 履歴ファイル一覧を表示
claude-history --list

# 最新の履歴を表示（デフォルト：カラー）
claude-history

# モノクロ表示
claude-history --no-color

# 特定のファイルを指定
claude-history /path/to/history.jsonl

# 特定のプロジェクトから選択
claude-history --project my-project

# ファイルに出力
claude-history --output formatted_history.txt

# 強制カラー出力（リダイレクト時でも色付き）
claude-history --force-color > colored_file.txt
```

### インストール不要の直接実行

```bash
# プロジェクトディレクトリに移動
cd pretty-history-claude-code

# 対話的メニューモード（推奨）
python3 src/claude_history.py --menu
# または引数なしで実行
python3 src/claude_history.py

# 対話的ファイル選択のみ
python3 src/claude_history.py --select

# 履歴ファイル一覧を表示
python3 src/claude_history.py --list

# 最新の履歴を表示（デフォルト：カラー）
python3 src/claude_history.py

# モノクロ表示
python3 src/claude_history.py --no-color

# 特定のファイルを指定
python3 src/claude_history.py /path/to/history.jsonl

# 特定のプロジェクトから選択
python3 src/claude_history.py --project my-project

# ファイルに出力
python3 src/claude_history.py --output formatted_history.txt

# 強制カラー出力（リダイレクト時でも色付き）
python3 src/claude_history.py --force-color > colored_file.txt
```

### シェルエイリアス設定（便利）

```bash
# ~/.bashrc または ~/.zshrc に追加
alias claude-history='python3 /path/to/pretty-history-claude-code/src/claude_history.py'

# その後は普通のコマンドとして使用可能
claude-history --select
claude-history --list
```

## 機能

- 🌈 **完全カラー対応** - 鮮やかな色分けで見やすく表示
- 🎨 **テーマシステム** - 4つの表示テーマから選択可能
- 🖱️ **対話的選択** - プロジェクト・ファイルを対話的に選択（--select）
- 🔍 **スマート検索** - セッション履歴を自動検出・一覧表示
- 📊 **完全なコンテキスト** - ツール使用、結果、コスト、実行時間、diff表示
- 🚀 **依存関係なし** - Python標準ライブラリのみ使用
- 💻 **クロスプラットフォーム** - Windows、macOS、Linuxで動作
- ⚙️  **柔軟な出力** - カラー/モノクロ、ファイル/標準出力対応

## 🎨 表示オプション

複数のテーマと表示オプションをサポート：

```bash
# カラー表示（デフォルト）
claude-history

# モノクロ表示  
claude-history --no-color

# カラーコード付きファイル出力（共有用）
claude-history --force-color > colored_output.txt
```


### 🚀 クイックスタート

**1. インストール済みの場合**
```bash
claude-history            # メニューモード（推奨）
claude-history --menu     # メニューモード（明示的）
claude-history --select   # ファイル選択のみ
claude-history --list     # 履歴一覧
```

**2. インストール不要で直接実行**
```bash
cd pretty-history-claude-code
python3 src/claude_history.py            # メニューモード（推奨）
python3 src/claude_history.py --menu     # メニューモード（明示的）
python3 src/claude_history.py --select   # ファイル選択のみ
python3 src/claude_history.py --list     # 履歴一覧
```

**3. エイリアス設定済みの場合**
```bash
# ~/.bashrc に追加後
alias claude-history='python3 /path/to/pretty-history-claude-code/src/claude_history.py'

# 通常のコマンドとして使用
claude-history            # メニューモード
claude-history --select   # ファイル選択のみ
```

## Requirements

- Python 3.6+
- No external dependencies

## Acknowledgments

This tool is inspired by various conversation interfaces and terminal applications, but is an independent open-source project. It is **not affiliated with, endorsed by, or officially connected with Anthropic, Claude, or any related services** in any way.

The visual styling draws inspiration from common terminal UI patterns and is designed to provide a pleasant reading experience for conversation logs stored in JSONL format.

## Legal Disclaimer

- This software is provided for **educational and personal use only**
- Users are **solely responsible** for ensuring their use complies with any applicable terms of service of the platforms whose data they are viewing
- The developers assume **no responsibility** for any misuse of this tool or violations of third-party terms of service
- This tool does **not** access, modify, or transmit any data beyond local file reading and display

## License

MIT License - see LICENSE file for complete details

**Additional Notices**: See NOTICE file for important disclaimers and usage guidelines

**Summary**: Free to use, modify, and distribute under standard MIT License terms. Users should review the NOTICE file for important disclaimers regarding responsible use and third-party compliance.
