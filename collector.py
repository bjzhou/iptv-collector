
import re
import time
import requests
import subprocess
import concurrent.futures
import asyncio
import aiohttp
from urllib.parse import urlparse

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
    name = re.sub(r'_\d+M\d+', '', name)
    name = re.sub(r'\(.*?\)', '', name) 
    return name.strip()

def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]

def filter_playlist(playlist, keywords, blacklist=None):
    """Filters playlist based on keywords and blacklist."""
    filtered = []
    if blacklist is None:
        blacklist = []
        
    for item in playlist:
        # Check blacklist first
        is_blacklisted = False
        for blocked in blacklist:
             if blocked in item['url']:
                 is_blacklisted = True
                 break
        if is_blacklisted:
            continue

        cleaned_name = clean_name(item['name'])
        item['clean_name'] = cleaned_name
        for i, keyword in enumerate(keywords):
            if keyword in cleaned_name:
                item['priority'] = i
                filtered.append(item)
                break
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

def check_stream(item):
    """Checks stream validity and latency."""
    url = item['url']
    start_time = time.time()
    
    # Try FFmpeg first
    cmd = [
        "ffmpeg", 
        "-i", url, 
        "-t", "1", 
        "-f", "null", 
        "-", 
        "-v", "error"
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
        latency = (time.time() - start_time) * 1000
        item['latency'] = latency
        return item
    except FileNotFoundError:
        # Fallback to requests if ffmpeg missing
        pass
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # FFmpeg failed implies stream is invalid, do not fallback
        return None

    # Fallback to requests if ffmpeg missing (indented to match try block if pass executed)
    try:
        with requests.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            # Read a small chunk to ensure it's streaming
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    break
            latency = (time.time() - start_time) * 1000
            item['latency'] = latency
            return item
    except Exception:
        return None

def process_playlists(urls, keywords, blacklist=None, skip_validation=False):
    """Main processing logic."""
    all_channels = []
    
    # 1. Fetch and Parse
    for url in urls:
        print(f"Processing {url}...")
        content = fetch_content(url)
        if not content:
            continue
            
        if url.endswith(".m3u") or ".m3u" in url:
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        all_channels.extend(channels)
        
    print(f"Total channels found: {len(all_channels)}")

    # 2. Filter & Clean
    filtered_channels = filter_playlist(all_channels, keywords, blacklist)
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
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
