import json, urllib.request, uuid

BASE = "http://127.0.0.1:3000/api"

def call(method, path, body=None):
    token = globals().get("tok")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")

u = uuid.uuid4().hex[:6]
call("POST", "/auth/register", body={"email": f"ww{u}@t.com", "username": f"ww{u}", "password": "pass12345"})
_, r = call("POST", "/auth/login", body={"email": f"ww{u}@t.com", "password": "pass12345"})
tok = r["access_token"]

# create 3 words
_, w1 = call("POST", "/words/", {"english": "abandon", "chinese": "放弃"})
_, w2 = call("POST", "/words/", {"english": "ability", "chinese": "能力"})
_, w3 = call("POST", "/words/", {"english": "advocate", "chinese": "主张"})

# summary before any review
_, s = call("GET", "/learning/wrong-words/summary")
print("summary-before:", "open=", s["open_count"], "today=", s["today_wrong_count"], "due=", s["weak_due_count"])

def review(wid, result):
    return call("POST", "/learning/reviews", {"word_id": wid, "result": result})

# w1 wrong x2, w2 wrong x1, w3 correct
review(w1["id"], "wrong")
review(w1["id"], "wrong")
review(w2["id"], "close")
review(w3["id"], "correct")

# list wrong-words
_, lst = call("GET", "/learning/wrong-words")
print("wrong list:", [(i["english"], i["wrong_count"], i["status"]) for i in lst["items"]], "total=", lst["total"])

# summary after
_, s = call("GET", "/learning/wrong-words/summary")
print("summary-after:", "open=", s["open_count"], "today=", s["today_wrong_count"], "due=", s["weak_due_count"])

# weak_only due (w1,w2 are open; w3 excluded)
_, due = call("GET", "/learning/reviews/due?weak_only=true")
print("weak_only due:", [i["english"] for i in due["items"]])

# resolve w2 -> open count decreases
_, r = call("POST", f"/learning/wrong-words/{w2['id']}/resolve")
_, lst2 = call("GET", "/learning/wrong-words")
print("after resolve w2, status:", [(i["english"], i["status"]) for i in lst2["items"]])
_, due2 = call("GET", "/learning/reviews/due?weak_only=true")
print("weak_only due after resolve:", [i["english"] for i in due2["items"]])

# delete w1
_, r = call("DELETE", f"/learning/wrong-words/{w1['id']}")
_, lst3 = call("GET", "/learning/wrong-words")
print("after delete w1:", [(i["english"]) for i in lst3["items"]])

# resolve/delete nonexistent -> 404
s, r = call("POST", "/learning/wrong-words/xxxx/resolve")
print("resolve nonexistent should be 404 or 404:", s)
# a correct-then-wrong again re-opens
review(w1["id"], "wrong")
_, lst4 = call("GET", "/learning/wrong-words")
print("re-wrong w1 re-added:", [(i["english"], i["status"]) for i in lst4["items"]])