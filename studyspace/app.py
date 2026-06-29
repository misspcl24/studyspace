from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
import hashlib
import uuid
from datetime import date, datetime

PROXY_PREFIX = "/proxy/5000"

app = Flask(__name__)
app.secret_key = "studyspace-secret-key-2026"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def purl(endpoint, **kwargs):
    """url_for that prepends the proxy prefix so links work through the proxy."""
    return PROXY_PREFIX + url_for(endpoint, **kwargs)


@app.context_processor
def inject_helpers():
    nav_courses = []
    if "username" in session:
        u = load_user(session["username"])
        if u:
            nav_courses = u.get("courses", [])
    return dict(purl=purl, proxy_prefix=PROXY_PREFIX, nav_courses=nav_courses)


@app.template_filter('fmt_duration')
def fmt_duration(secs):
    if not secs:
        return '0m'
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


@app.template_filter('fmt_date')
def fmt_date(date_str):
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%b %d, %Y')
    except Exception:
        return date_str or ''


def predir(endpoint, **kwargs):
    return redirect(url_for(endpoint, **kwargs))


# ── Helpers ───────────────────────────────────────────────────────────────────

def user_file(username):
    return os.path.join(DATA_DIR, f"{username}.json")


def load_user(username):
    path = user_file(username)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_user(data):
    path = user_file(data["username"])
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def logged_in():
    return "username" in session


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if logged_in():
        return predir("dashboard")
    return predir("login")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        user = load_user(username)
        if user and user["password_hash"] == hash_password(password):
            session["username"] = username
            return predir("dashboard")
        error = "Wrong username or password."
    return render_template("login.html", error=error)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        if not username or not password:
            error = "Username and password can't be empty."
        elif load_user(username):
            error = "That username is already taken."
        else:
            save_user({
                "username": username,
                "password_hash": hash_password(password),
                "courses": []
            })
            session["username"] = username
            return predir("dashboard")
    return render_template("signup.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return predir("login")


# ── Dashboard ─────────────────────────────────────────────────────────────────


@app.route("/dashboard")
def dashboard():
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])

    # Pass raw items — JS filters to this week using the browser's local date
    sidebar_items = []
    for course in user.get("courses", []):
        for a in course.get("assignments", []):
            if a.get("due"):
                sidebar_items.append({
                    "date": a["due"],
                    "title": a["title"],
                    "sublabel": course["name"],
                    "color": "#7c3aed",
                })
    for e in user.get("calendar_events", []):
        if e.get("date"):
            time_str = e.get("start_time") or ("All day" if e.get("all_day") else "")
            sidebar_items.append({
                "date": e["date"],
                "title": e["title"],
                "sublabel": time_str,
                "color": e.get("color") or "#7c3aed",
            })

    return render_template("dashboard.html", user=user, sidebar_items=sidebar_items)


@app.route("/course/add", methods=["POST"])
def add_course():
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    user["courses"].append({
        "id": str(uuid.uuid4()),
        "name": request.form["name"].strip(),
        "description": request.form["description"].strip(),
        "grade": "",
        "assignments": [],
        "notes": [],
        "flashcards": [],
        "resources": []
    })
    save_user(user)
    return predir("dashboard")


@app.route("/course/<course_id>")
def course(course_id):
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    c = next((c for c in user["courses"] if c["id"] == course_id), None)
    if not c:
        return predir("dashboard")
    course_sidebar_items = []
    for a in c.get("assignments", []):
        if a.get("due"):
            course_sidebar_items.append({
                "date": a["due"],
                "title": a["title"],
                "sublabel": a.get("type", "assignment").capitalize(),
                "color": "#7c3aed",
            })
    for e in user.get("calendar_events", []):
        if e.get("date") and e.get("course_id") == course_id:
            time_str = e.get("start_time") or ("All day" if e.get("all_day") else "")
            course_sidebar_items.append({
                "date": e["date"],
                "title": e["title"],
                "sublabel": time_str,
                "color": e.get("color") or "#7c3aed",
            })
    return render_template("course.html", user=user, course=c, course_sidebar_items=course_sidebar_items)


@app.route("/course/<course_id>/delete", methods=["POST"])
def delete_course(course_id):
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    user["courses"] = [c for c in user["courses"] if c["id"] != course_id]
    save_user(user)
    return predir("dashboard")


@app.route("/course/<course_id>/update", methods=["POST"])
def update_course(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    for c in user["courses"]:
        if c["id"] == course_id:
            data = request.get_json()
            if "grade" in data:
                c["grade"] = data["grade"]
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404

@app.route("/course/<course_id>/edit", methods=["POST"])
def edit_course(course_id):
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    for c in user["courses"]:
        if c["id"] == course_id:
            c["name"] = request.form["name"].strip()
            c["description"] = request.form["description"].strip()
            save_user(user)
            return predir("course", course_id=course_id)
    return predir("dashboard")

@app.route("/course/<course_id>/assignment/add", methods=["POST"])
def add_assignment(course_id):
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    for c in user["courses"]:
        if c["id"] == course_id:
            c["assignments"].append({
                "id": str(uuid.uuid4()),
                "title": request.form["title"].strip(),
                "due": request.form.get("due", ""),
                "type": request.form.get("type", "assignment"),
                "progress": 0
            })
            save_user(user)
            break
    return predir("course", course_id=course_id)


@app.route("/course/<course_id>/icon", methods=["POST"])
def update_course_icon(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    icon = request.get_json().get("icon", "").strip()
    for c in user["courses"]:
        if c["id"] == course_id:
            c["icon"] = icon
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/assignment/<assignment_id>/delete", methods=["POST"])
def delete_assignment(course_id, assignment_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    for c in user["courses"]:
        if c["id"] == course_id:
            c["assignments"] = [a for a in c["assignments"] if a["id"] != assignment_id]
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/assignment/<assignment_id>/progress", methods=["POST"])
def update_progress(course_id, assignment_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    for c in user["courses"]:
        if c["id"] == course_id:
            for a in c["assignments"]:
                if a["id"] == assignment_id:
                    a["progress"] = int(request.get_json().get("progress", 0))
                    save_user(user)
                    return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/study-log")
def study_log():
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    all_sessions = []
    for c in user.get("courses", []):
        for s in c.get("study_sessions", []):
            all_sessions.append({**s, "course_name": c["name"], "course_id": c["id"]})
    all_sessions.sort(key=lambda x: x.get("date", ""), reverse=True)
    preselect = request.args.get("course", "")
    return render_template("study_log.html",
                           sessions=all_sessions,
                           preselect_course=preselect)


@app.route("/course/<course_id>/study/save", methods=["POST"])
def save_study_session(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            c.setdefault("study_sessions", [])
            c["study_sessions"].append({
                "id":         str(uuid.uuid4()),
                "name":       data.get("name", "").strip(),
                "date":       data.get("date", ""),
                "duration":   int(data.get("duration", 0)),
                "break_time": int(data.get("break_time", 0)),
                "target":     data.get("target"),
                "notes":      data.get("notes", "").strip()
            })
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/assignment/<assignment_id>/update", methods=["POST"])
def update_assignment(course_id, assignment_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            for a in c["assignments"]:
                if a["id"] == assignment_id:
                    if "description" in data:
                        a["description"] = data["description"]
                    save_user(user)
                    return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/assignment/<assignment_id>/comment", methods=["POST"])
def add_assignment_comment(course_id, assignment_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            for a in c["assignments"]:
                if a["id"] == assignment_id:
                    a.setdefault("comments", [])
                    a["comments"].append({
                        "id":   str(uuid.uuid4()),
                        "text": data.get("text", "").strip(),
                        "date": date.today().isoformat()
                    })
                    save_user(user)
                    return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/flashcard/add", methods=["POST"])
def add_flashcard(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            c.setdefault("flashcards", [])
            c["flashcards"].append({
                "id":    str(uuid.uuid4()),
                "front": data.get("front", "").strip(),
                "back":  data.get("back", "").strip()
            })
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/quiz/add", methods=["POST"])
def add_quiz(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            c.setdefault("quizzes", [])
            c["quizzes"].append({
                "id":    str(uuid.uuid4()),
                "title": data.get("title", "").strip(),
                "url":   data.get("url", "").strip()
            })
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/study-note/add", methods=["POST"])
def add_study_note(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            c.setdefault("study_notes", [])
            c["study_notes"].append({
                "id":    str(uuid.uuid4()),
                "title": data.get("title", "").strip(),
                "type":  data.get("type", "regular")
            })
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/course/<course_id>/resource/add", methods=["POST"])
def add_resource(course_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for c in user["courses"]:
        if c["id"] == course_id:
            c.setdefault("resources", [])
            c["resources"].append({
                "id":    str(uuid.uuid4()),
                "title": data.get("title", "").strip(),
                "url":   data.get("url", "").strip(),
                "type":  data.get("type", "website")
            })
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/profile")
def profile():
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    return render_template("profile.html", user=user)

@app.route("/calendar")
def calendar():
    if not logged_in():
        return predir("login")
    user = load_user(session["username"])
    events = []
    for course in user.get("courses", []):
        for a in course.get("assignments", []):
            if a.get("due"):
                events.append({
                    "id": a["id"],
                    "title": a["title"],
                    "date": a["due"],
                    "type": a.get("type", "assignment"),
                    "course": course["name"],
                    "course_id": course["id"],
                    "course_icon": course.get("icon", ""),
                    "source": "assignment"
                })
    for e in user.get("calendar_events", []):
        events.append(dict(e, source="manual"))
    return render_template("calendar.html", user=user, events=events)


@app.route("/calendar/event/add", methods=["POST"])
def add_calendar_event():
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    if "calendar_events" not in user:
        user["calendar_events"] = []
    data = request.get_json()
    title = data.get("title", "").strip()
    date = data.get("date", "").strip()
    if not title or not date:
        return jsonify({"ok": False}), 400
    user["calendar_events"].append({
        "id":         str(uuid.uuid4()),
        "title":      title,
        "date":       date,
        "end_date":   data.get("end_date") or None,
        "start_time": data.get("start_time") or None,
        "end_time":   data.get("end_time") or None,
        "all_day":    bool(data.get("all_day", False)),
        "repeat":     data.get("repeat", "none"),
        "color":      data.get("color") or "#7c3aed",
        "course_id":  data.get("course_id") or None,
        "notes":      data.get("notes") or None,
        "type":       "event"
    })
    save_user(user)
    return jsonify({"ok": True})


@app.route("/calendar/event/<event_id>", methods=["PUT"])
def update_calendar_event(event_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    data = request.get_json()
    for i, e in enumerate(user.get("calendar_events", [])):
        if e["id"] == event_id:
            user["calendar_events"][i] = {
                "id":         event_id,
                "title":      (data.get("title") or e["title"]).strip(),
                "date":       data.get("date") or e["date"],
                "end_date":   data.get("end_date") or None,
                "start_time": data.get("start_time") or None,
                "end_time":   data.get("end_time") or None,
                "all_day":    bool(data.get("all_day", False)),
                "repeat":     data.get("repeat", "none"),
                "color":      data.get("color") or "#7c3aed",
                "course_id":  data.get("course_id") or None,
                "notes":      data.get("notes") or None,
                "type":       "event"
            }
            save_user(user)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/calendar/event/<event_id>", methods=["DELETE"])
def delete_calendar_event(event_id):
    if not logged_in():
        return jsonify({"ok": False}), 401
    user = load_user(session["username"])
    original = len(user.get("calendar_events", []))
    user["calendar_events"] = [e for e in user.get("calendar_events", []) if e["id"] != event_id]
    if len(user["calendar_events"]) < original:
        save_user(user)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
