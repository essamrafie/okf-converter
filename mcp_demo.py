#!/usr/bin/env python3
"""MCP demo: call OKF server via direct HTTP."""
import subprocess, json, sys, re

def mcp_init():
    cmd = ["curl", "-s", "-D", "-", "-X", "POST",
           "http://localhost:8006/mcp",
           "-H", "Content-Type: application/json",
           "-H", "Accept: application/json, text/event-stream",
           "-d", json.dumps({"jsonrpc":"2.0","method":"initialize",
                             "params":{"protocolVersion":"2024-11-05",
                                       "capabilities":{},
                                       "clientInfo":{"name":"demo","version":"1"}},
                             "id":1})]
    out = subprocess.check_output(cmd, text=True)
    for line in out.split("\n"):
        if "mcp-session-id" in line.lower():
            return line.split(":")[-1].strip().strip("\r")
    return ""

def mcp_call(sid, name, args):
    cmd = ["curl", "-s", "-X", "POST",
           "http://localhost:8006/mcp",
           "-H", "Content-Type: application/json",
           "-H", "Accept: application/json, text/event-stream",
           "-H", f"MCP-Session-Id: {sid}",
           "-d", json.dumps({"jsonrpc":"2.0","method":"tools/call",
                             "params":{"name":name,"arguments":args},
                             "id":2})]
    out = subprocess.check_output(cmd, text=True)
    for line in out.split("\n"):
        m = re.match(r"^data: (.+)", line)
        if m:
            return json.loads(m.group(1))
    return None

def pp(data):
    """Pretty-print nested dict."""
    return json.dumps(data, indent=2, ensure_ascii=False)

sid = mcp_init()
print(f"Session: {sid}\n")

# STEP 1: List bundle
print("=== okf_list_bundle ===")
r = mcp_call(sid, "okf_list_bundle",
             {"bundle_dir": "/Users/essamrafie/dev/okf-converter/okf-bundle"})
data = json.loads(r["result"]["content"][0]["text"])
print(f"  {data['total_concepts']} concepts in {data['bundle']}")
for c in data["concepts"]:
    print(f"    {c['title']} -> {c['path']}")
print()

# STEP 2: Search
print('=== okf_search_bundle(query="Assignment 2.1") ===')
r = mcp_call(sid, "okf_search_bundle",
             {"bundle_dir": "/Users/essamrafie/dev/okf-converter/okf-bundle",
              "query": "Assignment 2.1"})
data = json.loads(r["result"]["content"][0]["text"])
concept = data["results"][0]["concept"]
print(f"  Match: {concept}")
print()

# STEP 3: Get concept
print(f"=== okf_get_concept('{concept}') ===")
r = mcp_call(sid, "okf_get_concept",
             {"bundle_dir": "/Users/essamrafie/dev/okf-converter/okf-bundle",
              "concept_path": concept})
item = json.loads(r["result"]["content"][0]["text"])
print(f"  Frontmatter:")
print(f"    Type:        {item['frontmatter']['type']}")
print(f"    Title:       {item['frontmatter']['title']}")
print(f"    Tags:        {item['frontmatter']['tags']}")
print(f"    Source file: {item['frontmatter']['source_file']}")
print(f"  Body ({item['body_chars']} chars):")
for line in item["body"].split("\n")[:12]:
    if line.strip():
        print(f"    {line[:130]}")
print()

# STEP 4-5: More searches
for q in ["Stable Diffusion", "Qwen3", "OpenShift"]:
    print(f'=== okf_search_bundle(query="{q}") ===')
    r = mcp_call(sid, "okf_search_bundle",
                 {"bundle_dir": "/Users/essamrafie/dev/okf-converter/okf-bundle",
                  "query": q})
    data = json.loads(r["result"]["content"][0]["text"])
    print(f"  Matches: {data['matches']}")
    for hit in data["results"][:2]:
        print(f"    [{hit['concept']}] \"{hit['snippet'][:80]}\"")
    print()
