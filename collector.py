
import re
import json
import time
import requests
import subprocess
import concurrent.futures
import asyncio
import aiohttp
import os
import socket
from urllib.parse import urljoin, urlparse

_ipv6_support = None

def is_ipv6_supported():
    """Checks if the current environment supports IPv6."""
    global _ipv6_support
    if _ipv6_support is not None:
        return _ipv6_support
    
    try:
        # Try to connect to a reliable IPv6 host (Alibaba DNS)
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.connect(("2400:3200::1", 80))
        sock.close()
        _ipv6_support = True
        print("IPv6 is supported.")
    except Exception:
        _ipv6_support = False
        print("IPv6 is not supported.")
    return _ipv6_support

def is_ipv6_url(url):
    """Checks if the URL is a literal IPv6 URL."""
    try:
        hostname = urlparse(url).hostname
        return hostname and ":" in hostname
    except Exception:
        return False

def fetch_content(url):
    """Fetches content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_m3u(content):
    """Parses M3U content into a list of dictionaries with attributes."""
    playlist = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # Parsing attributes using regex
            # #EXTINF:-1 tvg-id="CCTV1" tvg-name="CCTV1" tvg-logo="url",CCTV-1
            info = line
            attributes = {}
            
            # Extract duration and remaining info
            # Usually #EXTINF:duration key="value"...,Name
            # Or #EXTINF:duration,Name
            
            # Basic parsing of the line
            # distinct between params and name (last comma)
            last_comma_index = info.rfind(',')
            if last_comma_index != -1:
                meta_part = info[:last_comma_index]
                name = info[last_comma_index+1:].strip()
            else:
                meta_part = info
                name = "Unknown"
            
            # Extract key="value" pairs
            for match in re.finditer(r'([a-zA-Z0-9-]+)="([^"]*)"', meta_part):
                key = match.group(1)
                value = match.group(2)
                attributes[key] = value
            
            url = ""
            # Look ahead for URL
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("#"):
                    url = next_line
                    i = j
                    break
            
            if url:
                item = {"name": name, "url": url, "attributes": attributes}
                playlist.append(item)
        elif line and not line.startswith("#"):
             pass
        i += 1
    return playlist

def parse_txt(content):
    """Parses TXT content (format: name,url) into a list."""
    playlist = []
    for line in content.splitlines():
        if "," in line and "#genre#" not in line:
            parts = line.split(",")
            name = parts[0].strip()
            url = parts[1].strip()
            # TXT has no extra attributes
            playlist.append({"name": name, "url": url, "attributes": {}})
    return playlist

def clean_name(name):
    """Cleans channel name by removing specific suffixes."""
    name = re.sub(r'_.+M.+', '', name)
    name = re.sub(r'\(.*?\)', '', name) 
    return name.strip()

def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]

def filter_playlist(playlist, keywords, blacklist=None, whitelist=None):
    """Filters playlist based on keywords and blacklist."""
    filtered = []
    if blacklist is None:
        blacklist = []
        
    for item in playlist:
        # 1. Check whitelist first
        is_whitelisted = False
        if whitelist:
            for w in whitelist:
                if w in item['url']:
                    is_whitelisted = True
                    break
        
        # 2. Check blacklist (only if not whitelisted)
        if not is_whitelisted:
            is_blacklisted = False
            for blocked in blacklist:
                 if blocked in item['url']:
                     if 'source_url' in item and blocked in item['source_url']:
                         continue
                     is_blacklisted = True
                     break
            if is_blacklisted:
                continue

        # 3. Match keywords
        cleaned_name = clean_name(item['name'])
        matched_keyword = False
        for i, keyword in enumerate(keywords):
            if keyword in cleaned_name:
                item['priority'] = i
                item['keyword'] = keyword
                item['clean_name'] = cleaned_name
                
                # Check IPv6 support
                if is_ipv6_url(item['url']) and not is_ipv6_supported():
                    # We might still want to skip if IPv6 is not supported, 
                    # even if whitelisted. But if it's whitelisted, maybe the user knows what they're doing.
                    # Let's keep IPv6 check for now.
                    continue
                    
                filtered.append(item)
                matched_keyword = True
                break
        
        # 4. If whitelisted but no keyword match, still keep it
        if not matched_keyword and is_whitelisted:
            item['priority'] = len(keywords)
            item['keyword'] = '白名单'
            item['clean_name'] = cleaned_name
            filtered.append(item)
    return filtered

async def check_url_async(session, item, timeout=5):
    """Async check for URL validity (status 200)."""
    url = item['url']
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                return item
    except Exception:
        pass
    return None

async def filter_playlist_async(items, concurrency=500):
    """Filters playlist asynchronously."""
    semaphore = asyncio.Semaphore(concurrency)
    valid_items = []
    
    async def bound_check(session, item):
        async with semaphore:
            return await check_url_async(session, item)

    print(f"Async checking {len(items)} links with concurrency {concurrency}...")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [bound_check(session, item) for item in items]
        results = await asyncio.gather(*tasks)
        
    for res in results:
        if res:
            valid_items.append(res)
            
    print(f"Async check finished in {time.time() - start_time:.2f}s. Retained {len(valid_items)}/{len(items)} channels.")
    return valid_items

def run_async_check(items):
    """Wrapper to run async check in sync context."""
    if hasattr(asyncio, 'run'):
        return asyncio.run(filter_playlist_async(items))
    else:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(filter_playlist_async(items))

def parse_resolution(stdout_data):
    """从 ffprobe 的 JSON 输出中提取分辨率"""
    try:
        data = json.loads(stdout_data)
        streams = data.get('streams', [])
        if not streams:
            # print("Failed to parse resolution: No streams found")
            return None
        width = streams[0].get('width') or streams[0].get('coded_width', 0)
        height = streams[0].get('height') or streams[0].get('coded_height', 0)
        if width > 0 and height > 0:
            return f"{width}x{height}"
    except Exception as e:
        print(f"Failed to parse resolution: {e}")
        pass
    return None

def check_stream(item):
    url = item['url']
    start_time = time.time()
    
    headers = {
        "User-Agent": "iPhone",
        "Referer": f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
    }

    # 逻辑：判断是否 M3U8 -> (如果是) 解析分片 -> Python 下载流前段 -> 塞给 ffprobe
    try:
        segment_url = url
        is_m3u8 = False

        # 1. 探测链接类型 (避免直接下载大文件)
        try:
            with requests.get(url, headers=headers, stream=True, timeout=10) as r_probe:
                if r_probe.status_code != 200:
                    return None
                
                # 读取头部检测是否有 M3U8 特征
                first_chunk = next(r_probe.iter_content(chunk_size=2048), b"")
                content_str = first_chunk.decode('utf-8', errors='ignore')
                if "#EXTM3U" in content_str or "#EXTINF" in content_str:
                    is_m3u8 = True
        except Exception:
            return None

        if is_m3u8:
            # 2. 如果是 M3U8，需获取完整列表提取分片
            r_playlist = requests.get(url, headers=headers, timeout=10)
            if r_playlist.status_code != 200:
                return None

            lines = r_playlist.text.splitlines()
            segment_path = next((line.strip() for line in lines if line.strip() and not line.startswith("#")), None)
            
            if not segment_path:
                return None
                
            segment_url = urljoin(url, segment_path)

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "v:0",
            # "-f", "mpegts",
            "-analyzeduration", "100000", 
            "-probesize", "512000",
            "-i", "-"
        ]
        
        # 3. 启动 ffprobe，准备接收管道数据
        ffprobe_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        try:
            # 4. 请求分片数据并通过管道写入 ffprobe
            chunk_data = bytearray()
            target_size = 512 * 1024 # 目标 512KB
            with requests.get(segment_url, headers=headers, stream=True, timeout=10) as r_segment:
                if r_segment.status_code != 200:
                    return None
                
                start_download = time.time()

                for chunk in r_segment.iter_content(chunk_size=4096):
                    if time.time() - start_download > 8: # 硬性限制：下载过程不能超过 8 秒
                        break 
                    
                    if chunk:
                        chunk_data.extend(chunk)
                        if len(chunk_data) >= target_size:
                            break
                
                if len(chunk_data) == 0:
                    return None
                
                try:
                    stdout_data, _ = ffprobe_process.communicate(input=chunk_data, timeout=10)
                except subprocess.TimeoutExpired:
                    ffprobe_process.kill()
                    print(f"Timeout while checking segment: {segment_url}")
                    return None

            # 5. 解析结果
            res = parse_resolution(stdout_data)
            if res:
                item['latency'] = int((time.time() - start_time) * 1000)
                item['resolution'] = res
                return item
        finally:
            if ffprobe_process.poll() is None:
                ffprobe_process.kill()

    except Exception as e:
        # print(f"Deep check failed: {e}")
        return None

    return None

def process_playlists(urls, keywords, blacklist=None, whitelist=None, skip_validation=False):
    """Main processing logic."""
    all_channels = []
    
    # 1. Fetch and Parse
    for url in urls:
        print(f"Processing {url}...")
        content = fetch_content(url)
        if not content:
            continue
            
        if "#EXTM3U" in content:
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        
        # Add source_url to each channel
        for channel in channels:
            channel['source_url'] = url
            
        all_channels.extend(channels)
        
    print(f"Total channels found: {len(all_channels)}")

    # 2. Filter & Clean
    filtered_channels = filter_playlist(all_channels, keywords, blacklist, whitelist)
    print(f"Channels after filtering: {len(filtered_channels)}")

    # 3. Deduplicate
    unique_urls = {}
    for item in filtered_channels:
        # Prefer items with more attributes (like logo) if URLs are same
        if item['url'] not in unique_urls:
             unique_urls[item['url']] = item
        else:
            # If new item has attributes and old doesn't, swap?
            # For simplicity, just strict URL dedup for now.
            pass
    
    deduped_channels = list(unique_urls.values())
    print(f"Channels after deduplication: {len(deduped_channels)}")
    
    # 4. Async Pre-check (Fast)
    if not skip_validation:
        print("Running fast async pre-check...")
        if whitelist:
            to_check = []
            skipped = []
            for item in deduped_channels:
                url = item['url']
                if any(w in url for w in whitelist):
                    skipped.append(item)
                else:
                    to_check.append(item)
            
            if to_check:
                checked = run_async_check(to_check)
            else:
                checked = []
            
            deduped_channels = checked + skipped
            print(f"Whitelisted {len(skipped)} channels skipped async check.")
        else:
            deduped_channels = run_async_check(deduped_channels)
    
    # 5. Validate & Match Latency (Deep Check)
    valid_channels = []
    
    if skip_validation:
        print("Skipping validation as requested.")
        for item in deduped_channels:
            item['latency'] = 0
            valid_channels.append(item)
    else:
        print("Validating channels with FFmpeg (this still takes some time)...")
        
        from tqdm import tqdm
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            futures = {executor.submit(check_stream, item): item for item in deduped_channels}
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), unit="stream"):
                result = future.result()
                if result:
                    valid_channels.append(result)
    
    print(f"Valid channels: {len(valid_channels)}")

    # 6. Sort
    # Priority 1: Keyword order (priority)
    # Priority 2: Natural Name Order (CCTV1 < CCTV2 < CCTV10)
    # Priority 3: Latency
    valid_channels.sort(key=lambda x: (x['priority'], natural_key(x['clean_name']), x['latency']))

    return valid_channels

def generate_m3u(channels):
    """Generates M3U content."""
    # Add EPG Source
    epg_url = "http://epg.51zmt.top:8000/e.xml"
    lines = [f'#EXTM3U x-tvg-url="{epg_url}"']
    
    for item in channels:
        name = item['clean_name']
        attrs = item['attributes']
        url = item['url']
        
        # Ensure tvg-name matches the clean name if not present
        if 'tvg-name' not in attrs:
            attrs['tvg-name'] = name
        if 'tvg-logo' not in attrs:
             attrs['tvg-logo'] = "https://tb.zbds.top/logo/" + name + ".png" # Reasonable default? Or leave empty. User asked to add info. 
             # Actually, if we don't have it, better to leave it or rely on valid sources.
             # The user asked to "Increase EPG and Logo info". 
             # Let's keep existing attributes. If missing, maybe add minimal group-title.
        
        # Build attribute string
        attr_str = ""
        for k, v in attrs.items():
            if k == "group-title":
                continue
            attr_str += f' {k}="{v}"'
        
        lines.append(f"#EXTINF:-1{attr_str},{name}")
        lines.append(url)
    return "\n".join(lines)

def generate_txt(channels):
    """Generates TXT content (name,url format) with genre grouping."""
    lines = []
    current_genre = None
    for item in channels:
        genre = item.get('keyword', '其他')
        if genre != current_genre:
            lines.append(f"{genre},#genre#")
            current_genre = genre
        
        lines.append(f"{item['clean_name']},{item['url']}")
    
    return "\n".join(lines)
