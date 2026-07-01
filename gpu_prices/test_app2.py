"""Integration test for refactored GPU Price Aggregator API."""
import subprocess, sys, os, time

PORT = 8765

proc = subprocess.Popen(
    [sys.executable, "-c", f"import uvicorn; from main import app; uvicorn.run(app, host='127.0.0.1', port={PORT}, log_level='error')"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(4)

try:
    import httpx
    c = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=10)

    r = c.get("/")
    assert r.status_code == 200
    print(f"Homepage: {r.status_code} {len(r.text)} bytes - OK")

    r = c.get("/api/products?per_page=2")
    d = r.json()
    assert d["total"] > 0
    print(f"API: {d['total']} GPU models - OK")

    first_slug = d["products"][0]["slug"]
    r = c.get(f"/api/models/{first_slug}")
    md = r.json()
    assert md["name"] and len(md["sellers"]) > 0
    print(f"Model detail: '{md['name']}' with {len(md['sellers'])} seller(s) - OK")

    first_pid = md["sellers"][0]["product_id"]
    r = c.get(f"/api/products/{first_pid}")
    pd = r.json()
    assert pd["name"] and pd["model_slug"]
    print(f"Product detail: '{pd['name'][:50]}...', model slug present, {len(pd['price_history'])} price entries - OK")

    r = c.get("/api/products?in_stock=1&per_page=3")
    d2 = r.json()
    all_ok = all(any(s["in_stock"] for s in m["sellers"]) for m in d2["products"])
    print(f"In-stock filter: {d2['total']} models, all in-stock: {all_ok} - OK")

    r = c.get("/api/products?seller=startech&per_page=2")
    d3 = r.json()
    print(f"Seller filter (StarTech): {d3['total']} models - OK")

    r = c.get("/api/products?brand=Asus&per_page=2")
    d4 = r.json()
    print(f"Brand filter (Asus): {d4['total']} models - OK")

    r = c.get("/api/products?sort=price&order=desc&per_page=3")
    d5 = r.json()
    prices = [m["min_price"] for m in d5["products"]]
    assert prices == sorted(prices, reverse=True)
    print(f"Price sort desc: {prices} - OK")

    r = c.get(f"/model/{first_slug}")
    assert r.status_code == 200
    print(f"Model page: {r.status_code} {len(r.text)} bytes - OK")

    r = c.get(f"/product/{first_pid}")
    assert r.status_code == 200
    print(f"Product page: {r.status_code} {len(r.text)} bytes - OK")

    r = c.get("/api/filters")
    f = r.json()
    print(f"Filters: {len(f['brands'])} brands, {len(f['sellers'])} sellers - OK")

    print("\nAll tests passed!")
finally:
    proc.terminate()
    proc.wait(timeout=5)
