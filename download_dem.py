#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载全国 30m DEM(Copernicus DEM GLO-30,AWS 公开数据,无需账号)。

特性:
  - 按 1°x1° 瓦片下载 COG 压缩 GeoTIFF(平均 10~25MB/片,约为 SRTM .hgt 的一半)
  - 默认排除西藏、海南(按省级行政边界精确排除,不会误伤青海/川西/滇西北/南疆)
  - --only-provinces 可只下载轨迹实际覆盖的省份,体积最小
  - 断点续传:已下载完成的瓦片自动跳过
  - 无需 awscli,直接 HTTP 下载

用法:
  python download_dem.py --dry-run                 # 只统计瓦片数量和预计体积
  python download_dem.py                           # 下载全国(不含西藏、海南)
  python download_dem.py --workers 16              # 提高并发
  python download_dem.py --only-provinces 北京 河北 山西   # 只下载指定省份
  python download_dem.py --exclude 西藏 海南       # 自定义排除名单(默认值)
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

S3_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
DATAV = "https://geo.datav.aliyun.com/areas_v3/bound/{}.json"
CHINA_ADCODE = "100000"

# 中国陆地范围(瓦片网格,1°x1°)
LAT_RANGE = range(17, 54)   # 覆盖至 53.x°N(漠河)
LON_RANGE = range(73, 136)  # 覆盖至 135.x°E(抚远)

AVG_TILE_MB = 15  # 粗略估算用

PROVINCES = {
    "北京": "110000", "天津": "120000", "河北": "130000", "山西": "140000",
    "内蒙古": "150000", "辽宁": "210000", "吉林": "220000", "黑龙江": "230000",
    "上海": "310000", "江苏": "320000", "浙江": "330000", "安徽": "340000",
    "福建": "350000", "江西": "360000", "山东": "370000", "河南": "410000",
    "湖北": "420000", "湖南": "430000", "广东": "440000", "广西": "450000",
    "海南": "460000", "重庆": "500000", "四川": "510000", "贵州": "520000",
    "云南": "530000", "西藏": "540000", "陕西": "610000", "甘肃": "620000",
    "青海": "630000", "宁夏": "640000", "新疆": "650000", "台湾": "710000",
}


# ---------------- 边界数据 ----------------

def fetch_boundary(code: str, cache_dir: str):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{code}.json")
    if not os.path.exists(path):
        tmp = path + ".part"
        urllib.request.urlretrieve(DATAV.format(code), tmp)
        os.replace(tmp, path)
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    return gj["features"][0]["geometry"]


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def point_in_geom(x, y, geom):
    """geom: GeoJSON Polygon/MultiPolygon。只测外环,对省界/国界判定足够。"""
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return False
    for poly in polys:
        if point_in_ring(x, y, poly[0]):
            return True
    return False


# ---------------- 瓦片选择 ----------------

def tile_name(lat: int, lon: int) -> str:
    return f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"


def tile_url(lat: int, lon: int) -> str:
    name = tile_name(lat, lon)
    return f"{S3_BASE}/{name}/{name}.tif"


def select_tiles(only_codes=None, exclude_codes=()):
    china = fetch_boundary(CHINA_ADCODE, "data/boundaries")
    only_geoms = [fetch_boundary(c, "data/boundaries") for c in only_codes] if only_codes else []
    excl_geoms = [fetch_boundary(c, "data/boundaries") for c in exclude_codes]

    tiles = []
    for lat in LAT_RANGE:
        for lon in LON_RANGE:
            cx, cy = lon + 0.5, lat + 0.5
            # 跳过南海中部(海南已默认排除,且司机轨迹不会出现在 open sea)
            if cy < 20.5 and cx > 117.5:
                continue
            corners = [(lon, lat), (lon + 1, lat), (lon, lat + 1), (lon + 1, lat + 1), (cx, cy)]
            if not any(point_in_geom(x, y, china) for x, y in corners):
                continue
            if any(point_in_geom(cx, cy, g) for g in excl_geoms):
                continue
            if only_geoms and not any(point_in_geom(cx, cy, g) for g in only_geoms):
                continue
            tiles.append((lat, lon))
    return tiles


# ---------------- 下载 ----------------

def download_tile(lat: int, lon: int, out_dir: str, retries: int = 3, progress=None):
    """progress(received_bytes, total_bytes):下载过程中周期回调;total 未知时为 0。"""
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, tile_name(lat, lon) + ".tif")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return ("skip", dest, 0)
    tmp = f"{dest}.{os.getpid()}.{threading.get_ident()}.part"   # 唯一临时名,避免并发下载互相覆盖

    def _hook(count, bs, total):
        if progress:
            progress(count * bs, total if total and total > 0 else 0)

    for attempt in range(retries):
        try:
            urllib.request.urlretrieve(tile_url(lat, lon), tmp, reporthook=_hook)
            os.replace(tmp, dest)
            return ("ok", dest, os.path.getsize(dest))
        except Exception as e:
            if attempt == retries - 1:
                if os.path.exists(tmp):
                    os.remove(tmp)
                return ("fail", tile_url(lat, lon), 0)
            time.sleep(2 * (attempt + 1))


def main():
    ap = argparse.ArgumentParser(description="全国 30m DEM 下载器(Copernicus GLO-30)")
    ap.add_argument("--out-dir", default="data/dem", help="DEM 存放目录(默认 data/dem)")
    ap.add_argument("--workers", type=int, default=8, help="并发下载数(默认 8)")
    ap.add_argument("--dry-run", action="store_true", help="只统计,不下载")
    ap.add_argument(
        "--only-provinces", nargs="+", metavar="省名或adcode",
        help="只下载指定省份(轨迹覆盖范围有限时用,体积最小)",
    )
    ap.add_argument(
        "--exclude", nargs="+", default=["西藏", "海南"], metavar="省名或adcode",
        help="排除的省份(默认: 西藏 海南)",
    )

    def to_code(name):
        if name in PROVINCES:
            return PROVINCES[name]
        if name.isdigit() and name in PROVINCES.values():
            return name
        # 兼容简写:藏→西藏
        for k, v in PROVINCES.items():
            if k.startswith(name) or name in k:
                return v
        ap.error(f"未知省份: {name}")

    args = ap.parse_args()

    only_codes = [to_code(p) for p in args.only_provinces] if args.only_provinces else None
    if only_codes:
        excl_codes = ()
    else:
        excl_codes = tuple(to_code(p) for p in args.exclude)

    print("正在拉取行政边界(首次运行会缓存到 data/boundaries/) ...")
    tiles = select_tiles(only_codes, excl_codes)
    est_gb = len(tiles) * AVG_TILE_MB / 1024
    print(f"待下载瓦片: {len(tiles)} 个,预计约 {est_gb:.1f} GB")
    if args.dry_run:
        for lat, lon in tiles:
            print(" ", tile_name(lat, lon))
        return

    if not tiles:
        print("没有需要下载的瓦片。")
        return

    t0, done, failed, skipped, nbytes = time.time(), 0, 0, 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(download_tile, lat, lon, args.out_dir): (lat, lon) for lat, lon in tiles}
        for fut in as_completed(futs):
            status, what, size = fut.result()
            done += 1
            if status == "ok":
                nbytes += size
            elif status == "skip":
                skipped += 1
            else:
                failed += 1
                print(f"\n[失败] {what}", file=sys.stderr)
            if done % 20 == 0 or done == len(tiles):
                el = time.time() - t0
                speed = nbytes / 1024 / 1024 / el if el else 0
                print(f"\r进度 {done}/{len(tiles)}(跳过 {skipped},失败 {failed})"
                      f"  新下载 {nbytes / 1024**3:.2f} GB  {speed:.1f} MB/s",
                      end="", flush=True)
    print()
    if failed:
        print(f"完成,但有 {failed} 个瓦片失败,重新运行本脚本可续传补齐。", file=sys.stderr)
        sys.exit(1)
    print("全部完成。")


if __name__ == "__main__":
    main()
