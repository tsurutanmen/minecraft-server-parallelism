# Minecraft サーバーは何コア使えるか：マルチコア化と GPU 化の実測

Minecraft Java Edition 26.1.2 のサーバーで、次の4つを同じ PC で測りました。

1. チャンク生成を、マルチコアと GPU でどこまで速くできるか
2. モブの処理（押し合い・経路探索）は GPU に向いているか
3. Paper・Folia・ShreddedPaper を同じ負荷で比べると、どう違うか
4. サーバーの処理を「種類ごと」に別々のコアへ分けると、最大で何倍になるか

すべての数字は `results/` の生データから `summarize.py` で作った [`results/SUMMARY.md`](results/SUMMARY.md) に基づいています。

## English summary

Measurements on one desktop (i5-14600KF 14C/20T, 32 GB, RTX 3060 12 GB), Minecraft Java 26.1.2.

- **Chunk generation.** Vanilla uses about 1.1 cores and makes 22.8 chunks/s. C2ME spreads the work over about 11.6 cores (15.1x, excluding one outlier run). Its OpenCL add-on adds about 1.4x on top, for 20.9x in total. Terrain matches vanilla closely, but differs slightly more than two vanilla runs differ from each other, mainly near the surface.
- **Mobs on the GPU.** At normal mob counts the GPU is not worth it. Pushing only beats one CPU core at a few thousand mobs, and beats all cores at around 16,000. fp32 is unsafe: the maximum relative error reached 0.11-0.12 in dense crowds of 64k-256k mobs and 0.23 with 256k spread-out mobs. For mobs chasing one player, one shared flow field takes 0.16 ms on one CPU core. Per-mob A* takes 18.5 ms for 1,000 mobs. The GPU flow field (2 ms) is slower than the CPU one.
- **Folia vs ShreddedPaper vs Paper.** With default settings, Folia puts players closer than about 1.5-1.9 km apart into one region. With players spread out (1,920 blocks apart), Folia and ShreddedPaper both hold 20 TPS at 4,800 villagers, where Paper drops to about 4. With players clustered (256 blocks apart), Folia falls to 0.24-0.26 TPS in a single region, slower than Paper. ShreddedPaper still keeps 17.3-17.7 TPS.
- **Splitting by kind of work.** On Paper, villager brain logic takes 66-70% of the main thread. Giving each kind of work its own core can therefore make a tick at most about 1.5x faster (Amdahl bound), and only about 1.1x faster if the split is simply "mobs" vs "everything else". The work has to be split by place or by entity instead.

## 環境

| 項目 | 内容 |
|---|---|
| CPU | Intel Core i5-14600KF（14コア・20スレッド） |
| メモリ | 32GB |
| GPU | NVIDIA GeForce RTX 3060 12GB（OpenCL 3.0 / CUDA） |
| OS | Windows 11 |
| Java | Eclipse Temurin 25.0.4.1 |
| サーバー | Fabric 0.19.5 + fabric-api 0.155.3 / Paper 26.1.2 build 74 / Folia 26.1.2 build 8 / ShreddedPaper 26.1.2 build 18 |
| MOD | C2ME 0.4.0-alpha.0.62、C2ME OpenCL Acceleration Module（同じ版）、ScalableLux 0.3.0-alpha.0.2、Chunky 1.5.3、spark 1.10.187 |
| ボット | mineflayer 4.39.0（オフラインモード・`127.0.0.1` のみ） |
| シード | 20260927 |

## 1. チャンク生成

半径1,024ブロック（16,641チャンク）を Chunky で作り、1秒あたりのチャンク数を測りました。4つの構成を交互に3回ずつ回しています。

| 構成 | 1秒あたりのチャンク数 | 本家比 |
|---|---|---|
| 本家相当（Fabric のみ） | 23.4 / 23.2 / 21.8 | 1.0倍 |
| C2ME | 355.4 / 331.4（1回目の136.4は外れ値） | 15.1倍 |
| C2ME + ScalableLux | 362.9 / 338.9（1回目の188.4は外れ値） | 15.4倍 |
| C2ME + OpenCL（GPU） | 483.1 / 457.6 / 489.8 | 20.9倍 |

外れ値とした2回は、本家の構成が止まるときの保存（6〜7分かかる）の直後に走った回です。

**使ったコア数**（半径512ブロック）：本家相当 1.13・1.14コア、C2ME 11.58コア、C2ME + GPU 11.10・11.32コア（20スレッド中）。本家が遅いのは1コアしか使わないからで、速くなった分の大部分はマルチコア化によるものです。

### 地形は本家と同じか

中心の625チャンク（6,144万ブロック）をブロック単位で突き合わせました（`compare_worlds.py`）。本家は同じシードでも毎回少し違う地形を作る（[MC-55596](https://mojira.dev/MC-55596)）ので、本家どうしのズレを基準にしています。

| 比べた組 | ブロックの種類が違う | 地形の形（地面・液体・空気）が違う | 形の違い（高さ56〜79） |
|---|---|---|---|
| 本家 対 本家（基準） | 0.293% | 0.0076% | 0.011% |
| 本家 対 C2ME | 0.399% | 0.0116% | 0.044% |
| 本家 対 C2ME + GPU | 0.448% | 0.0146% | 0.071% |
| C2ME + GPU 対 C2ME + GPU | 0.396% | 0.0108% | 0.026% |

ブロックの種類のズレの大半は、葉・落ち葉・鉱石・岩の塊など、あとから置かれる飾りです。地形の形のズレは GPU 版で約7,000ブロックに1つです。本家どうしの揺れより大きく、地表付近で差が目立ちます。これは C2ME-ocl の説明にある「バイオームの境界がまれに1〜2ブロックずれる」と合います。各組1回ずつの比較です。

## 2. モブの処理を GPU に載せる

どちらの実験でも、CPU（numba）と GPU（CuPy の自作 CUDA カーネル）で同じアルゴリズムを動かしています。

**押し合い**（`mobs/push_bench.py`）は、本家の `Entity.push` の式をそのまま使いました。押し合いは速度に足すだけなので、処理の順番に結果が左右されません。GPU の時間には、CPU とのデータのやり取りも含めています。

| 場面 | 匹数 | CPU 1コア | CPU 全コア | GPU（倍精度） |
|---|---|---|---|---|
| 4×4ブロックの囲い | 1,600 | 4.2 ms | 0.742 ms | 6.51 ms |
| 広い範囲に密集 | 16,000 | 5.3 ms | 1.92 ms | 1.77 ms |
| 広い範囲に密集 | 256,000 | 144 ms | 44.4 ms | 20.4 ms |

- GPU には約0.7ミリ秒の固定費があります。数千匹までは CPU のほうが速いです。
- 普通の精度（float32）では、最大相対誤差が、密集した6万4千〜25万6千匹で0.11〜0.12、散らばった25万6千匹で0.23になりました。「0.6ブロック以内か」の判定がひっくり返るためです。倍精度なら誤差は10⁻¹⁶程度です。

**経路探索**（`mobs/path_bench.py`：128×128の地図・壁25%・全員が同じプレイヤーを追う場合）

| 匹数 | 1匹ずつ A*（CPU 1コア） | 1匹ずつ A*（CPU 全コア） | フローフィールド（CPU 1コア） | フローフィールド（GPU） |
|---|---|---|---|---|
| 10 | 0.153 ms | 0.194 ms | 0.161 ms | 2 ms |
| 1,000 | 18.5 ms | 8.7 ms | 0.161 ms | 2 ms |
| 10,000 | 188 ms | 76.9 ms | 0.161 ms | 2 ms |

効いているのは GPU ではなく、「全員分をまとめて1回計算する」というやり方の変更です。ただし、全員が同じ目標を追うときにしか使えません。どの方法でも、道の長さは全モブで BFS の正解と一致しました。

## 3. Paper・Folia・ShreddedPaper の比較

負荷の条件は次のとおりです。
- 16か所に、ボットを2体ずつ（合計32体）置きました。
- 各地点のリーダーのボットが、村人を `/summon` で出しました。
- 難易度はピースフルです。
- Folia の `threaded-regions.threads` と ShreddedPaper の `thread-count` は、どちらも12にしました。
- TPS は各サーバー自身の報告です（Folia は地域の中央値、ほかは1分平均）。
- 使ったコア数は、サーバーのプロセスの CPU 時間を経過時間で割ったものです。

### Folia が地域を分ける距離

初期設定（grid-exponent 4・view-distance 6）では、**1,536ブロック以内にいるプレイヤーは1つの地域にまとめられ、1,920ブロック以上離れると分かれました**（[`results/folia_region_merge.txt`](results/folia_region_merge.txt)）。

### 散らばっている場合（16か所・1,920ブロック間隔）

| 村人 | Paper | Folia | ShreddedPaper |
|---|---|---|---|
| 1,600匹 | TPS 12.2 / 12.9・1.3コア | TPS 20.0 / 20.0・4.2コア | TPS 20.0 / 20.0・3.6〜3.8コア |
| 4,800匹 | TPS 4.1 / 3.9・1.3コア | TPS 20.0 / 20.0・8.0〜8.3コア | TPS 20.0 / 20.0・7.0〜7.5コア |
| 9,600匹 | TPS 2.1 / 2.0・1.3コア | TPS 11.7 / 13.8・13.3〜14.5コア | TPS 11.7 / 12.0・9.3コア |

### 散らばっている場合と、集まっている場合（村人4,800匹）

| サーバー | 1,920ブロック間隔 | 256ブロック間隔 |
|---|---|---|
| Paper | TPS 2.90 / 3.30・1.4コア | TPS 2.50 / 3.60・1.3コア |
| Folia | TPS 20.00 / 20.00・8.7〜9.4コア・16地域 | **TPS 0.24 / 0.26・1.2コア・1地域** |
| ShreddedPaper | TPS 19.30 / 20.00・7.7〜8.6コア | **TPS 17.30 / 17.70・5.3コア** |

- Folia は、プレイヤーが集まると1つの地域になり、Paper より遅くなりました。
- ShreddedPaper は、チャンク単位で鍵をかける方式なので、集まっていても並列が残りました。

## 4. 処理の種類ごとにコアを分けたら

Paper の本流スレッド（`Server thread`）を JFR で120秒記録し、各サンプルを「何の処理の中にいたか」で分類しました（`analyze_jfr.py`）。村人4,800匹、4回分です。

| 処理 | 割合 |
|---|---|
| モブ：頭脳（Brain） | 65.9〜69.6% |
| モブ：その他 | 10.8〜12.6% |
| モブ：押し合い | 4.7〜5.5% |
| モブ：移動・衝突 | 4.3〜4.7% |
| モブ：経路探索 | 1.7〜4.1% |
| 自然発生・ランダムな更新 | 2.6〜3.4% |
| チャンクの仕組み・追跡 | 1.8〜2.2% |
| レッドストーンなどの予約された更新 | 0.2〜0.6% |

種類ごとに別々のコアで動かすと、1回の更新は一番重い種類より短くはなりません。なので、上限は **1.44〜1.52倍**（アムダールの法則）です。「モブ」と「それ以外」に分けるだけなら、約1.1倍です。重いのは同じ種類の処理の大量のくり返しなので、場所やモブごとに分けるしかありません。

## 限界と注意

- 1台の PC で、各条件2〜3回ずつの計測です。ボットはサーバーと同じ PC で動いています（0.3〜0.6コアを使用）。
- 負荷は村人に偏っています。職業ブロックもベッドもない村人は、POI（ベッドや職業ブロック）を探し続けます。これは最悪に近い条件で、頭脳の割合を押し上げています。取引所やレッドストーン装置が中心のサーバーでは、内訳が変わります。
- 世界は C2ME + GPU で作ってから、全サーバーで同じものを使いました。Paper 系は、起動時にこの世界のフォルダの形式を移し替えています。
- Canvas（Folia のフォーク）は、公式のダウンロードページから自動で取得できなかったので、比べていません。
- モブの GPU 実験は、本家のサーバーの外で式と格子を再現したものです。Java のサーバーに組み込んだ場合の通信や同期の手間は含みません。

## 失敗した回も残しています

| ファイル | 何が起きたか |
|---|---|
| `results/invalid_chunkgen_run1_overlapping_save.jsonl` | 本家の保存が終わる前に次の構成が始まり、計測が重なった。捨てて取り直した |
| `results/servers_run1.jsonl` | **Folia の行は無効**。Folia には `/function` がなく（Unknown command）、データパックで出したつもりの村人が1匹も出ていなかった。Paper と ShreddedPaper の行は有効 |
| `results/servers_trials.jsonl` | 条件を固める前の試し運転。地点の間隔が短く、Folia が1地域だった |

## 再現のしかた

サーバー本体、Java、MOD、世界データは含めていません。それぞれの公式の配布元から取得してください。

1. Temurin JDK 25 を `jdk/` に展開する
2. 各サーバーを `servers/<名前>/server.jar` に置く
   - Fabric の構成：`vanilla`、`c2me`、`c2me-lux`、`c2me-ocl`
   - Paper 系：`paper`、`folia`、`shredded`
3. MOD を各サーバーの `mods/` に、Chunky を `plugins/` に置く
4. `server.properties` に次を設定する：`level-seed=20260927`、`online-mode=false`、`server-ip=127.0.0.1`、`pause-when-empty-seconds=0`
5. Minecraft の EULA に同意する場合は `eula.txt` に書く
6. `cd bots && npm install` を実行する

| やること | コマンド |
|---|---|
| チャンク生成の速さ | `./run_all.sh` |
| 地形の突き合わせ用の世界を作る | `./run_parity.sh` |
| 地形の突き合わせ | `python compare_worlds.py worlds/A worlds/B --radius-chunks 12 [--terrain]` |
| 共有の世界を作る | `python bench.py c2me-ocl 3050 --save-world-as shared_r3050`。そのあと `datapack/bench` を `worlds/shared_r3050/datapacks/` に写す |
| サーバー比較 | `./run_servers.sh` → `./run_folia_fix.sh` → `./run_kinds.sh` |
| モブ | `python mobs/push_bench.py` / `python mobs/path_bench.py`（CUDA 対応の GPU と CuPy が必要） |
| 表を作る | `python summarize.py > results/SUMMARY.md` |

Minecraft は Mojang Studios の商標です。このリポジトリは Mojang および Microsoft とは関係ありません。

コードは MIT ライセンスです。
