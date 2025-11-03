#!/usr/bin/env python3
"""
サーバーベンチマーク比較システム
Usage: python3 server_benchmark.py [--port 8000] [--db benchmark_results.json]
"""

import subprocess
import json
import time
import platform
import psutil
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import threading
import os
import uuid

class BenchmarkDatabase:
    def __init__(self, db_file="benchmark_results.json"):
        self.db_file = db_file
        self.data = self._load()
    
    def _load(self):
        """データベースファイルを読み込み"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except:
                return {"servers": []}
        return {"servers": []}
    
    def save(self):
        """データベースファイルに保存"""
        with open(self.db_file, 'w') as f:
            json.dump(self.data, indent=2, fp=f)
    
    def add_result(self, result):
        """ベンチマーク結果を追加"""
        result["id"] = str(uuid.uuid4())
        result["timestamp"] = datetime.now().isoformat()
        self.data["servers"].append(result)
        self.save()
        return result["id"]
    
    def get_all(self):
        """全ての結果を取得"""
        return self.data["servers"]
    
    def delete(self, result_id):
        """指定したIDの結果を削除"""
        self.data["servers"] = [s for s in self.data["servers"] if s.get("id") != result_id]
        self.save()
    
    def clear_all(self):
        """全ての結果を削除"""
        self.data = {"servers": []}
        self.save()


class BenchmarkRunner:
    def __init__(self):
        self.results = {}
        self.running = False
    
    def get_system_info(self):
        """システム情報を取得"""
        return {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "cpu_model": self._get_cpu_model(),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "total_memory_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }
    
    def _get_cpu_model(self):
        """CPU モデル名を取得"""
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        except:
            return "Unknown"
        return "Unknown"
    
    def run_cpu_benchmark(self):
        """CPU ベンチマーク (sysbench使用)"""
        print("Running CPU benchmark...")
        try:
            result = subprocess.run(
                ["sysbench", "cpu", "--cpu-max-prime=20000", "--threads=4", "run"],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout
            
            for line in output.split("\n"):
                if "events per second:" in line:
                    eps = float(line.split(":")[1].strip())
                    return {"events_per_second": eps, "status": "completed"}
            
            return {"events_per_second": 0, "status": "completed"}
        except subprocess.TimeoutExpired:
            return {"error": "Timeout", "status": "error"}
        except FileNotFoundError:
            return {"error": "sysbench not installed", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def run_memory_benchmark(self):
        """メモリ ベンチマーク"""
        print("Running memory benchmark...")
        try:
            result = subprocess.run(
                ["sysbench", "memory", "--memory-block-size=1M", 
                 "--memory-total-size=10G", "run"],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout
            
            for line in output.split("\n"):
                if "MiB/sec" in line and "transferred" in line:
                    parts = line.split("(")[1].split("MiB/sec")[0].strip()
                    return {"throughput_mib_per_sec": float(parts), "status": "completed"}
            
            return {"throughput_mib_per_sec": 0, "status": "completed"}
        except subprocess.TimeoutExpired:
            return {"error": "Timeout", "status": "error"}
        except FileNotFoundError:
            return {"error": "sysbench not installed", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def run_disk_benchmark(self):
        """ディスク ベンチマーク"""
        print("Running disk benchmark...")
        try:
            # 準備
            print("Preparing test files...")
            prep_result = subprocess.run(
                ["sysbench", "fileio", "--file-total-size=2G", "prepare"],
                capture_output=True, text=True, timeout=30
            )
            print(f"Prepare output: {prep_result.stdout[:200]}")
            
            # 実行
            print("Running fileio test...")
            result = subprocess.run(
                ["sysbench", "fileio", "--file-total-size=2G", 
                 "--file-test-mode=rndrw", "--time=10", "run"],
                capture_output=True, text=True, timeout=30
            )
            
            output = result.stdout
            print(f"Benchmark output:\n{output}")
            
            # クリーンアップ
            subprocess.run(
                ["sysbench", "fileio", "--file-total-size=2G", "cleanup"],
                capture_output=True, timeout=10
            )
            
            read_mib = write_mib = 0
            read_mb = write_mb = 0
            
            # 複数の出力フォーマットに対応
            for line in output.split("\n"):
                line_lower = line.lower()
                
                # 新しいフォーマット: "read, MiB/s:" または "reads/s:"
                if "read, mib/s:" in line_lower:
                    try:
                        read_mib = float(line.split(":")[1].strip())
                    except:
                        pass
                elif "written, mib/s:" in line_lower:
                    try:
                        write_mib = float(line.split(":")[1].strip())
                    except:
                        pass
                # 古いフォーマット: "Read 123.45Mb/sec"
                elif "read" in line_lower and ("mb/sec" in line_lower or "mb/s" in line_lower):
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "mb" in part.lower() and i > 0:
                                read_mb = float(parts[i-1])
                                read_mib = read_mb * 0.9537  # MB to MiB
                                break
                    except:
                        pass
                elif "written" in line_lower and ("mb/sec" in line_lower or "mb/s" in line_lower):
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "mb" in part.lower() and i > 0:
                                write_mb = float(parts[i-1])
                                write_mib = write_mb * 0.9537  # MB to MiB
                                break
                    except:
                        pass
                # さらに別のフォーマット: "reads: 1234 (12.34 per sec)"
                elif "reads:" in line_lower or "writes:" in line_lower:
                    try:
                        if "reads:" in line_lower and "per sec" in line_lower:
                            # This format doesn't give us MB/s directly
                            pass
                    except:
                        pass
            
            # もし値が取得できなかった場合、ddコマンドで簡易測定
            if read_mib == 0 and write_mib == 0:
                print("Sysbench format not recognized, trying dd command...")
                try:
                    # 書き込み速度測定
                    dd_write = subprocess.run(
                        ["dd", "if=/dev/zero", "of=/tmp/benchmark_test", 
                         "bs=1M", "count=1024", "conv=fdatasync"],
                        capture_output=True, text=True, timeout=30
                    )
                    for line in dd_write.stderr.split("\n"):
                        if "bytes" in line and "copied" in line:
                            parts = line.split(",")
                            for part in parts:
                                if "mb/s" in part.lower() or "gb/s" in part.lower():
                                    speed_str = part.strip().split()[0]
                                    write_mib = float(speed_str)
                                    break
                    
                    # 読み込み速度測定
                    dd_read = subprocess.run(
                        ["dd", "if=/tmp/benchmark_test", "of=/dev/null", "bs=1M"],
                        capture_output=True, text=True, timeout=30
                    )
                    for line in dd_read.stderr.split("\n"):
                        if "bytes" in line and "copied" in line:
                            parts = line.split(",")
                            for part in parts:
                                if "mb/s" in part.lower() or "gb/s" in part.lower():
                                    speed_str = part.strip().split()[0]
                                    read_mib = float(speed_str)
                                    break
                    
                    # クリーンアップ
                    subprocess.run(["rm", "-f", "/tmp/benchmark_test"], capture_output=True)
                except Exception as e:
                    print(f"DD benchmark failed: {e}")
            
            return {
                "read_mib_per_sec": read_mib,
                "write_mib_per_sec": write_mib,
                "status": "completed",
                "raw_output": output[:500]  # デバッグ用
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def run_network_benchmark(self):
        """ネットワーク ベンチマーク"""
        print("Running network benchmark...")
        results = {}
        
        # 基本的なネットワーク情報
        try:
            net_io = psutil.net_io_counters()
            results["total_bytes_sent_gb"] = round(net_io.bytes_sent / (1024**3), 2)
            results["total_bytes_recv_gb"] = round(net_io.bytes_recv / (1024**3), 2)
        except:
            pass
        
        # iperf3でスループット測定（サーバーモード）
        try:
            # 一時的にiperf3サーバーを起動して自己測定
            print("Testing network throughput with iperf3...")
            
            # ローカルループバックでのスループット測定
            server_proc = subprocess.Popen(
                ["iperf3", "-s", "-1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            time.sleep(1)  # サーバー起動待ち
            
            # クライアントとして接続
            result = subprocess.run(
                ["iperf3", "-c", "127.0.0.1", "-t", "5", "-J"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            server_proc.wait(timeout=2)
            
            if result.returncode == 0:
                import json as json_lib
                data = json_lib.loads(result.stdout)
                
                # 送信スループット (bits/sec to Mbps)
                send_bps = data["end"]["sum_sent"]["bits_per_second"]
                results["throughput_send_mbps"] = round(send_bps / 1000000, 2)
                
                # 受信スループット
                recv_bps = data["end"]["sum_received"]["bits_per_second"]
                results["throughput_recv_mbps"] = round(recv_bps / 1000000, 2)
        except subprocess.TimeoutExpired:
            results["throughput_error"] = "iperf3 timeout"
        except FileNotFoundError:
            results["throughput_error"] = "iperf3 not installed"
        except Exception as e:
            results["throughput_error"] = str(e)
        
        # pingでレイテンシ測定（ローカルゲートウェイ）
        try:
            print("Testing network latency...")
            # デフォルトゲートウェイを取得
            gw_result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if gw_result.returncode == 0:
                gateway = gw_result.stdout.split()[2]
                
                # ping実行
                ping_result = subprocess.run(
                    ["ping", "-c", "10", "-q", gateway],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if ping_result.returncode == 0:
                    output = ping_result.stdout
                    # rtt min/avg/max/mdev = 0.123/0.234/0.345/0.012 ms
                    for line in output.split("\n"):
                        if "rtt min/avg/max" in line or "round-trip min/avg/max" in line:
                            stats = line.split("=")[1].strip().split()[0]
                            min_ms, avg_ms, max_ms, mdev = stats.split("/")
                            results["latency_min_ms"] = float(min_ms)
                            results["latency_avg_ms"] = float(avg_ms)
                            results["latency_max_ms"] = float(max_ms)
                            results["latency_gateway"] = gateway
                            break
        except Exception as e:
            results["latency_error"] = str(e)
        
        # DNS解決速度テスト
        try:
            print("Testing DNS resolution speed...")
            import socket
            test_domains = ["google.com", "github.com", "cloudflare.com"]
            dns_times = []
            
            for domain in test_domains:
                start = time.time()
                socket.gethostbyname(domain)
                dns_times.append((time.time() - start) * 1000)  # ms
            
            results["dns_avg_ms"] = round(sum(dns_times) / len(dns_times), 2)
            results["dns_min_ms"] = round(min(dns_times), 2)
            results["dns_max_ms"] = round(max(dns_times), 2)
        except Exception as e:
            results["dns_error"] = str(e)
        
        results["status"] = "completed"
        return results
    
    def run_all_benchmarks(self, custom_name=None):
        """全ベンチマークを実行"""
        self.running = True
        self.results = {
            "system_info": self.get_system_info(),
            "benchmarks": {}
        }
        
        if custom_name:
            self.results["custom_name"] = custom_name
        
        self.results["benchmarks"]["cpu"] = self.run_cpu_benchmark()
        self.results["benchmarks"]["memory"] = self.run_memory_benchmark()
        self.results["benchmarks"]["disk"] = self.run_disk_benchmark()
        self.results["benchmarks"]["network"] = self.run_network_benchmark()
        
        self.results["completed_at"] = datetime.now().isoformat()
        self.running = False
        
        return self.results


class BenchmarkHTTPHandler(BaseHTTPRequestHandler):
    benchmark_runner = BenchmarkRunner()
    database = None
    
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_html().encode())
        
        elif self.path == "/api/benchmark":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            if not self.benchmark_runner.running:
                thread = threading.Thread(target=self.benchmark_runner.run_all_benchmarks)
                thread.start()
            
            response = {
                "running": self.benchmark_runner.running,
                "results": self.benchmark_runner.results
            }
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            response = {
                "running": self.benchmark_runner.running,
                "results": self.benchmark_runner.results
            }
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == "/api/history":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            all_results = self.database.get_all()
            self.wfile.write(json.dumps(all_results).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/api/save":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            custom_name = data.get("custom_name", "")
            
            if not self.benchmark_runner.running:
                thread = threading.Thread(
                    target=lambda: self._run_and_save(custom_name)
                )
                thread.start()
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode())
        
        elif self.path == "/api/delete":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            result_id = data.get("id")
            if result_id:
                self.database.delete(result_id)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "deleted"}).encode())
        
        elif self.path == "/api/clear":
            self.database.clear_all()
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "cleared"}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def _run_and_save(self, custom_name):
        """ベンチマークを実行して保存"""
        result = self.benchmark_runner.run_all_benchmarks(custom_name)
        self.database.add_result(result)
    
    def get_html(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Server Benchmark Comparison</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .controls {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        input[type="text"] {
            padding: 10px 15px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            flex: 1;
            min-width: 200px;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 14px;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover {
            background: #45a049;
        }
        button:disabled {
            background: #cccccc;
            cursor: not-allowed;
        }
        button.danger {
            background: #f44336;
        }
        button.danger:hover {
            background: #da190b;
        }
        button.secondary {
            background: #2196F3;
        }
        button.secondary:hover {
            background: #0b7dda;
        }
        .status {
            padding: 12px;
            border-radius: 5px;
            margin: 15px 0;
            text-align: center;
        }
        .status.running {
            background: #fff3cd;
            color: #856404;
        }
        .status.completed {
            background: #d4edda;
            color: #155724;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4CAF50;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .comparison-table {
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #4CAF50;
            color: white;
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .best-score {
            background: #c8e6c9;
            font-weight: bold;
        }
        .server-name {
            font-weight: bold;
            color: #2196F3;
            font-size: 16px;
        }
        .server-specs {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .metric-value {
            font-size: 16px;
            color: #333;
        }
        .metric-unit {
            font-size: 12px;
            color: #666;
            margin-left: 5px;
        }
        .action-btn {
            padding: 6px 12px;
            font-size: 12px;
            background: #f44336;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
        }
        .action-btn:hover {
            background: #da190b;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        .empty-state-icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ Server Benchmark Comparison</h1>
            <div class="controls">
                <input type="text" id="serverName" placeholder="サーバー名を入力 (例: Production Server 01)">
                <button onclick="runAndSaveBenchmark()">Run & Save Benchmark</button>
                <button class="secondary" onclick="loadHistory()">Refresh Results</button>
                <button class="danger" onclick="clearAllResults()">Clear All</button>
            </div>
            <div id="status"></div>
        </div>

        <div class="comparison-table">
            <h2 style="margin-bottom: 20px; color: #333;">Benchmark Results Comparison</h2>
            <div id="resultsTable"></div>
        </div>
    </div>

    <script>
        let pollInterval;

        function runAndSaveBenchmark() {
            const serverName = document.getElementById('serverName').value.trim();
            
            document.getElementById('status').innerHTML = 
                '<div class="status running">🔄 Running benchmarks...</div><div class="spinner"></div>';
            
            fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({custom_name: serverName})
            })
            .then(response => response.json())
            .then(data => {
                pollStatus();
            })
            .catch(error => {
                document.getElementById('status').innerHTML = 
                    '<div class="status" style="background: #f8d7da; color: #721c24;">Error: ' + error + '</div>';
            });
        }

        function pollStatus() {
            pollInterval = setInterval(() => {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        if (!data.running && data.results.completed_at) {
                            clearInterval(pollInterval);
                            document.getElementById('status').innerHTML = 
                                '<div class="status completed">✅ Benchmark completed and saved!</div>';
                            setTimeout(() => {
                                loadHistory();
                                document.getElementById('serverName').value = '';
                            }, 1000);
                        }
                    });
            }, 1000);
        }

        function loadHistory() {
            fetch('/api/history')
                .then(response => response.json())
                .then(data => {
                    displayComparison(data);
                });
        }

        function displayComparison(servers) {
            if (servers.length === 0) {
                document.getElementById('resultsTable').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📊</div>
                        <h3>No benchmark results yet</h3>
                        <p>Run your first benchmark to start comparing servers</p>
                    </div>
                `;
                return;
            }

            // 最高スコアを計算
            const maxCPU = Math.max(...servers.map(s => s.benchmarks?.cpu?.events_per_second || 0));
            const maxMemory = Math.max(...servers.map(s => s.benchmarks?.memory?.throughput_mib_per_sec || 0));
            const maxDiskRead = Math.max(...servers.map(s => s.benchmarks?.disk?.read_mib_per_sec || 0));
            const maxDiskWrite = Math.max(...servers.map(s => s.benchmarks?.disk?.write_mib_per_sec || 0));
            const maxNetworkThroughput = Math.max(...servers.map(s => {
                const net = s.benchmarks?.network;
                return Math.max(net?.throughput_send_mbps || 0, net?.throughput_recv_mbps || 0);
            }));
            const minLatency = Math.min(...servers.filter(s => s.benchmarks?.network?.latency_avg_ms).map(s => s.benchmarks.network.latency_avg_ms));
            const minDNS = Math.min(...servers.filter(s => s.benchmarks?.network?.dns_avg_ms).map(s => s.benchmarks.network.dns_avg_ms));

            let html = '<table><thead><tr>';
            html += '<th>Server Name</th>';
            html += '<th>CPU Model</th>';
            html += '<th>Cores</th>';
            html += '<th>Memory</th>';
            html += '<th>CPU Score<br><span style="font-weight:normal; font-size:11px">(events/sec)</span></th>';
            html += '<th>Memory Throughput<br><span style="font-weight:normal; font-size:11px">(MiB/s)</span></th>';
            html += '<th>Disk Read<br><span style="font-weight:normal; font-size:11px">(MiB/s)</span></th>';
            html += '<th>Disk Write<br><span style="font-weight:normal; font-size:11px">(MiB/s)</span></th>';
            html += '<th>Network Throughput<br><span style="font-weight:normal; font-size:11px">(Mbps)</span></th>';
            html += '<th>Latency<br><span style="font-weight:normal; font-size:11px">(ms)</span></th>';
            html += '<th>DNS<br><span style="font-weight:normal; font-size:11px">(ms)</span></th>';
            html += '<th>Tested At</th>';
            html += '<th>Action</th>';
            html += '</tr></thead><tbody>';

            servers.forEach(server => {
                const info = server.system_info;
                const bench = server.benchmarks;
                const displayName = server.custom_name || info.hostname;
                
                const cpuScore = bench?.cpu?.events_per_second || 0;
                const memScore = bench?.memory?.throughput_mib_per_sec || 0;
                const diskRead = bench?.disk?.read_mib_per_sec || 0;
                const diskWrite = bench?.disk?.write_mib_per_sec || 0;
                const networkThroughput = Math.max(bench?.network?.throughput_send_mbps || 0, bench?.network?.throughput_recv_mbps || 0);
                const latency = bench?.network?.latency_avg_ms;
                const dns = bench?.network?.dns_avg_ms;

                html += '<tr>';
                html += `<td><div class="server-name">${displayName}</div><div class="server-specs">${info.hostname}</div></td>`;
                html += `<td>${info.cpu_model}</td>`;
                html += `<td>${info.cpu_cores} cores<br><span style="font-size:11px; color:#666">(${info.cpu_threads} threads)</span></td>`;
                html += `<td>${info.total_memory_gb} GB</td>`;
                
                html += `<td class="${cpuScore === maxCPU ? 'best-score' : ''}"><span class="metric-value">${cpuScore.toFixed(2)}</span></td>`;
                html += `<td class="${memScore === maxMemory ? 'best-score' : ''}"><span class="metric-value">${memScore.toFixed(2)}</span></td>`;
                html += `<td class="${diskRead === maxDiskRead ? 'best-score' : ''}"><span class="metric-value">${diskRead.toFixed(2)}</span></td>`;
                html += `<td class="${diskWrite === maxDiskWrite ? 'best-score' : ''}"><span class="metric-value">${diskWrite.toFixed(2)}</span></td>`;
                
                // ネットワークスループット
                if (networkThroughput > 0) {
                    html += `<td class="${networkThroughput === maxNetworkThroughput ? 'best-score' : ''}">`;
                    html += `<span class="metric-value">${networkThroughput.toFixed(2)}</span>`;
                    if (bench?.network?.throughput_send_mbps && bench?.network?.throughput_recv_mbps) {
                        html += `<br><span style="font-size:10px; color:#666">↑${bench.network.throughput_send_mbps.toFixed(0)} / ↓${bench.network.throughput_recv_mbps.toFixed(0)}</span>`;
                    }
                    html += `</td>`;
                } else {
                    html += `<td><span style="color:#999; font-size:12px">${bench?.network?.throughput_error || 'N/A'}</span></td>`;
                }
                
                // レイテンシ
                if (latency) {
                    html += `<td class="${latency === minLatency ? 'best-score' : ''}">`;
                    html += `<span class="metric-value">${latency.toFixed(2)}</span>`;
                    html += `<br><span style="font-size:10px; color:#666">${bench.network.latency_min_ms.toFixed(2)}-${bench.network.latency_max_ms.toFixed(2)}</span>`;
                    html += `</td>`;
                } else {
                    html += `<td><span style="color:#999; font-size:12px">${bench?.network?.latency_error || 'N/A'}</span></td>`;
                }
                
                // DNS
                if (dns) {
                    html += `<td class="${dns === minDNS ? 'best-score' : ''}">`;
                    html += `<span class="metric-value">${dns.toFixed(2)}</span>`;
                    html += `<br><span style="font-size:10px; color:#666">${bench.network.dns_min_ms.toFixed(2)}-${bench.network.dns_max_ms.toFixed(2)}</span>`;
                    html += `</td>`;
                } else {
                    html += `<td><span style="color:#999; font-size:12px">${bench?.network?.dns_error || 'N/A'}</span></td>`;
                }
                
                const date = new Date(server.timestamp);
                html += `<td style="font-size: 12px;">${date.toLocaleString()}</td>`;
                html += `<td><button class="action-btn" onclick="deleteResult('${server.id}')">Delete</button></td>`;
                html += '</tr>';
            });

            html += '</tbody></table>';
            document.getElementById('resultsTable').innerHTML = html;
        }

        function deleteResult(id) {
            if (!confirm('この結果を削除しますか?')) return;
            
            fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id})
            })
            .then(() => loadHistory());
        }

        function clearAllResults() {
            if (!confirm('全ての結果を削除しますか? この操作は元に戻せません。')) return;
            
            fetch('/api/clear', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(() => loadHistory());
        }

        // 初期ロード
        loadHistory();
    </script>
</body>
</html>
        """
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Server Benchmark Comparison Tool")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port")
    parser.add_argument("--db", type=str, default="benchmark_results.json", 
                       help="Database file path")
    args = parser.parse_args()
    
    # データベース初期化
    BenchmarkHTTPHandler.database = BenchmarkDatabase(args.db)
    
    print("=" * 60)
    print("Server Benchmark Comparison Tool")
    print("=" * 60)
    print(f"\nDatabase file: {args.db}")
    print(f"Starting HTTP server on port {args.port}...")
    print(f"\nAccess the benchmark GUI at:")
    print(f"  http://localhost:{args.port}")
    print(f"  http://<server-ip>:{args.port}")
    print("\nPress Ctrl+C to stop the server\n")
    
    server = HTTPServer(("0.0.0.0", args.port), BenchmarkHTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    main()
