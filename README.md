# 🖥️ Server Benchmark Comparison Tool

複数のサーバーの性能を測定・比較するためのWebベースのベンチマークツールです。CPU、メモリ、ディスク、ネットワークの性能を測定し、直感的なGUIで結果を比較できます。


## ✨ 特徴

- **包括的なベンチマーク測定**
  - CPU性能（sysbench）
  - メモリスループット（sysbench）
  - ディスクI/O（sysbench）
  - ネットワーク性能（iperf3、ping、DNS）

- **直感的なWeb GUI**
  - ブラウザからアクセス可能
  - リアルタイムで結果を表示
  - 複数サーバーの結果を比較表示
  - 最高性能を自動ハイライト

- **柔軟なデータ管理**
  - JSONファイルで結果を保存
  - サーバー間でファイル共有可能
  - 個別/一括削除機能
  - カスタムサーバー名設定

## 📋 前提条件

- Ubuntu 20.04以降 または Debian系Linux
- Python 3.6以上
- rootまたはsudo権限（パッケージインストール時のみ）

## 🚀 インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/server_benchmark.git
cd server_benchmark
```

### 2. 依存パッケージのインストール

```bash
# システムパッケージ
sudo apt update
sudo apt install -y python3 python3-pip sysbench iperf3

# Pythonライブラリ
pip3 install psutil
```

## 📖 使い方

### 基本的な使用方法

```bash
# デフォルト設定で起動（ポート8000）
python3 server_benchmark.py

# カスタムポートで起動
python3 server_benchmark.py --port 8080

# カスタムデータベースファイルを指定
python3 server_benchmark.py --db /path/to/results.json
```

### Webインターフェースへのアクセス

ブラウザで以下のURLにアクセス：
- ローカル: `http://localhost:8000`
- リモート: `http://<server-ip>:8000`

### ベンチマークの実行

1. サーバー名を入力（例：「Production Server 01」）
2. 「Run & Save Benchmark」ボタンをクリック
3. ベンチマーク完了まで待機（通常2-3分）
4. 結果が自動的に表示・保存されます

## 📊 測定項目

### システム情報
- ホスト名
- OS バージョン
- CPU モデル
- CPU コア数/スレッド数
- 総メモリ容量

### CPU ベンチマーク
- **測定方法**: sysbench（素数計算）
- **指標**: Events per second
- **高いほど良い**

### メモリ ベンチマーク
- **測定方法**: sysbench（メモリ読み書き）
- **指標**: スループット（MiB/s）
- **高いほど良い**

### ディスク ベンチマーク
- **測定方法**: sysbench（ランダム読み書き）
- **指標**: 読み込み/書き込み速度（MiB/s）
- **高いほど良い**

### ネットワーク ベンチマーク
- **スループット**: iperf3でローカルループバック測定（Mbps）
- **レイテンシ**: デフォルトゲートウェイへのping（ms）
- **DNS解決速度**: 複数ドメインの名前解決時間（ms）

## 🔄 複数サーバーでの比較

### 方法1: 共有ストレージを使用

```bash
# Server 1
python3 server_benchmark.py --db /mnt/shared/benchmarks.json

# Server 2（同じファイルを参照）
python3 server_benchmark.py --db /mnt/shared/benchmarks.json
```

### 方法2: 手動でファイル転送

```bash
# Server 1でベンチマーク実行後
scp benchmark_results.json user@server2:/path/to/

# Server 2で同じファイルを使用
python3 server_benchmark.py --db /path/to/benchmark_results.json
```

### 方法3: Gitで管理

```bash
# 結果をコミット
git add benchmark_results.json
git commit -m "Add benchmark results for Server 1"
git push

# 別のサーバーでpull
git pull
python3 server_benchmark.py
```

## 🎨 結果の見方

比較表では、各項目で最高性能を達成したサーバーが**緑色**でハイライトされます。

| 列名 | 内容 | ベストスコア |
|------|------|-------------|
| Server Name | カスタム名またはホスト名 | - |
| CPU Model | プロセッサのモデル名 | - |
| Cores | 物理コア数（スレッド数） | - |
| Memory | 総メモリ容量（GB） | - |
| CPU Score | イベント/秒 | 最大値 |
| Memory Throughput | MiB/s | 最大値 |
| Disk Read | MiB/s | 最大値 |
| Disk Write | MiB/s | 最大値 |
| Network Throughput | Mbps（↑送信/↓受信） | 最大値 |
| Latency | 平均ms（最小-最大） | 最小値 |
| DNS | 平均ms（最小-最小） | 最小値 |

## ⚙️ コマンドラインオプション

```bash
python3 server_benchmark.py [OPTIONS]

Options:
  --port PORT       HTTPサーバーのポート番号（デフォルト: 8000）
  --db DATABASE     結果を保存するJSONファイルパス（デフォルト: benchmark_results.json）
  -h, --help        ヘルプを表示
```

## 🔒 ファイアウォール設定

リモートアクセスを許可する場合：

```bash
# UFW（Ubuntu/Debian）
sudo ufw allow 8000/tcp

# firewalld（CentOS/RHEL）
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 📁 ファイル構成

```
server-benchmark-tool/
├── server_benchmark.py       # メインスクリプト
├── benchmark_results.json    # 結果データベース（自動生成）
└── README.md                 # このファイル
```

## 🐛 トラブルシューティング

### sysbench not found エラー

```bash
sudo apt install -y sysbench
```

### iperf3 not found エラー

```bash
sudo apt install -y iperf3
```

### Permission denied エラー

```bash
# psutilのインストール
pip3 install --user psutil

# またはsudoで
sudo pip3 install psutil
```

### ポートが使用中

```bash
# 別のポートを指定
python3 server_benchmark.py --port 8080
```

## 🔧 カスタマイズ

### ベンチマーク設定の変更

`server_benchmark.py`内の以下のパラメータを編集：

```python
# CPU: 素数計算の上限
["sysbench", "cpu", "--cpu-max-prime=20000", "--threads=4", "run"]

# Memory: テストサイズ
["sysbench", "memory", "--memory-total-size=10G", "run"]

# Disk: ファイルサイズとテスト時間
["sysbench", "fileio", "--file-total-size=2G", "--time=10", "run"]

# Network: iperf3テスト時間
["iperf3", "-c", "127.0.0.1", "-t", "5"]
```

## 📝 注意事項

- **ネットワークスループット**はローカルループバック測定のため、実際のネットワーク速度ではなくシステムの最大処理能力を示します
- **ディスクベンチマーク**は一時ファイルを作成するため、十分な空き容量が必要です
- ベンチマーク実行中はシステムリソースを大量に消費します
- 本番環境で実行する場合は、サービスへの影響を考慮してください

## 🤝 コントリビューション

プルリクエストを歓迎します！大きな変更の場合は、まずIssueを開いて変更内容を議論してください。

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 👤 作者

Your Name - [@visionlanecom](https://twitter.com/visionlanecom)

## 🙏 謝辞

- [sysbench](https://github.com/akopytov/sysbench) - CPU、メモリ、ディスクベンチマーク
- [iperf3](https://github.com/esnet/iperf) - ネットワークスループット測定
- [psutil](https://github.com/giampaolo/psutil) - システム情報取得

---

⭐ このプロジェクトが役に立った場合は、スターをお願いします！
