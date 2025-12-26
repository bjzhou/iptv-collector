
import os
from collector import process_playlists, generate_m3u, generate_txt

def main():
    # 1. Read files
    try:
        with open("subscribe.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        
        with open("keywords.txt", "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        
        blacklist = []
        if os.path.exists("blacklist.txt"):
             with open("blacklist.txt", "r", encoding="utf-8") as f:
                blacklist = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        whitelist = []
        if os.path.exists("whitelist.txt"):
             with open("whitelist.txt", "r", encoding="utf-8") as f:
                whitelist = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"Loaded {len(urls)} subscription URLs, {len(keywords)} keywords, {len(blacklist)} blacklist items, and {len(whitelist)} whitelist items.")

    # 2. Process
    channels = process_playlists(urls, keywords, blacklist, whitelist=whitelist)

    # 3. Export
    if channels:
        # Export M3U
        m3u_content = generate_m3u(channels)
        with open("iptv.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"Successfully generated 'iptv.m3u' with {len(channels)} channels.")

        # Export TXT
        txt_content = generate_txt(channels)
        with open("iptv.txt", "w", encoding="utf-8") as f:
            f.write(txt_content)
        print(f"Successfully generated 'iptv.txt' with {len(channels)} channels.")
        
        # Verify first few lines
        print("\nPreview of generated M3U:")
        print("\n".join(m3u_content.splitlines()[:5]))
    else:
        print("No valid channels found.")

if __name__ == "__main__":
    main()
