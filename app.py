from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from google import genai
except ImportError:  # Lets the non-AI parts remain understandable in local tests.
    genai = None

APP_TITLE = "FocusFlow AI"
DEFAULT_MODEL = "gemini-flash-latest"
PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}
TASK_TYPES = ["Assignment", "Exam preparation", "Revision", "Personal goal", "Project", "Other"]

st.set_page_config(page_title=APP_TITLE, page_icon="📚", layout="wide")


# ----------------------------- Core logic -----------------------------
def days_until(due_date: date, today: date | None = None) -> int:
    """Return days until a due date; negative means the date has passed."""
    return (due_date - (today or date.today())).days


def task_sort_key(task: dict[str, Any], today: date | None = None) -> tuple[int, int, int, str]:
    """Sort unfinished work by overdue/urgency, priority, then deadline."""
    today = today or date.today()
    due = date.fromisoformat(task["due_date"])
    days_left = days_until(due, today)
    # Overdue work comes first; due today/tomorrow gets a stronger urgency score.
    urgency = 0 if days_left < 0 else (1 if days_left == 0 else (2 if days_left == 1 else 3))
    return (urgency, -PRIORITY_WEIGHT.get(task["priority"], 1), days_left, task["title"].lower())


def build_local_plan(tasks: list[dict[str, Any]], available_hours: float, today: date | None = None) -> dict[str, Any]:
    """Build a deterministic, testable plan that never exceeds available time."""
    today = today or date.today()
    pending = [task for task in tasks if not task["completed"]]
    pending.sort(key=lambda task: task_sort_key(task, today))
    remaining = round(max(0.0, float(available_hours)), 2)
    sessions: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for task in pending:
        estimated = float(task["hours"])
        if remaining <= 0:
            deferred.append(task)
            continue
        # Split long work into a manageable session, but don't schedule tiny fragments.
        session_hours = min(estimated, remaining, 2.0)
        if session_hours < 0.25:
            deferred.append(task)
            continue
        sessions.append({
            "title": task["title"],
            "subject": task["subject"],
            "task_type": task["task_type"],
            "due_date": task["due_date"],
            "priority": task["priority"],
            "hours": round(session_hours, 2),
            "remaining_after_session": round(max(0.0, estimated - session_hours), 2),
        })
        remaining = round(remaining - session_hours, 2)
        if estimated > session_hours:
            deferred.append(task)

    scheduled_hours = round(sum(session["hours"] for session in sessions), 2)
    return {
        "date": today.isoformat(),
        "available_hours": round(float(available_hours), 2),
        "scheduled_hours": scheduled_hours,
        "unused_hours": round(max(0.0, float(available_hours) - scheduled_hours), 2),
        "sessions": sessions,
        "deferred": deferred,
    }


def format_tasks_for_ai(tasks: list[dict[str, Any]], today: date | None = None) -> str:
    today = today or date.today()
    lines = []
    for task in tasks:
        due = date.fromisoformat(task["due_date"])
        if task["completed"]:
            status = "completed"
        elif due < today:
            status = "overdue"
        else:
            status = "pending"
        lines.append(
            f"- {task['title']} | subject: {task['subject']} | type: {task['task_type']} "
            f"| due: {task['due_date']} ({status}) | priority: {task['priority']} "
            f"| estimated hours remaining: {task['hours']}"
        )
    return "\n".join(lines) or "No tasks entered."


def generate_ai_advice(tasks: list[dict[str, Any]], available_hours: float, local_plan: dict[str, Any],
                       classes_text: str, goals_text: str, model_name: str) -> str:
    """Ask Gemini for advice while keeping the deterministic plan as a fallback."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            api_key = ""

    if not api_key:
        return (
            "### Local plan created\n"
            "Add a Gemini API key to enable AI coaching. The priority-based local plan is still available above.\n\n"
            "**Suggested next step:** Start with the first scheduled session, then update task completion and regenerate the plan."
        )
    if genai is None:
        return "The Gemini SDK is not installed. Run `pip install -r requirements.txt` and try again."

    prompt = f"""You are FocusFlow AI, a practical and encouraging study coach for university students.
Today is {date.today().isoformat()}. The student has {available_hours} study hours available today.

CLASSES / FIXED COMMITMENTS:
{classes_text.strip() or 'No class schedule provided.'}

PERSONAL GOALS:
{goals_text.strip() or 'No personal goals provided.'}

TASKS:
{format_tasks_for_ai(tasks)}

DETERMINISTIC PLAN (respect its total time limit):
{json.dumps([{k: s[k] for k in ('title', 'subject', 'hours', 'priority', 'due_date')} for s in local_plan['sessions']], ensure_ascii=False)}

Return concise Markdown with:
1. A short, encouraging overview.
2. A realistic ordered schedule with session durations and short breaks.
3. What to postpone if everything cannot fit.
4. A recovery suggestion for overdue/missed tasks.
5. One small personal-goal action if time allows.

Important: Never schedule completed tasks. Never exceed the available study hours. Treat classes as fixed commitments, not study hours. Do not invent exact class times if none were provided. Clearly mention that this is a suggested plan and the student should verify it.
"""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = getattr(response, "text", None)
        return text.strip() if text else "Gemini returned an empty response. Please try again."
    except Exception as exc:  # Friendly UI error; don't expose the key.
        return (
            "Gemini could not create coaching advice. Check your API key, model name, internet connection, "
            f"and API quota. The local plan is still available. (Details: {type(exc).__name__}: {exc})"
        )


# ----------------------------- Session state -----------------------------
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "classes" not in st.session_state:
    st.session_state.classes = []
if "goals" not in st.session_state:
    st.session_state.goals = ""
if "ai_advice" not in st.session_state:
    st.session_state.ai_advice = ""
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None


def mark_task(task_id: str, completed: bool) -> None:
    for task in st.session_state.tasks:
        if task["id"] == task_id:
            task["completed"] = completed
            break
    # Any changed task means the previous advice is now stale.
    st.session_state.ai_advice = ""
    st.session_state.last_plan = None


def delete_task(task_id: str) -> None:
    st.session_state.tasks = [t for t in st.session_state.tasks if t["id"] != task_id]
    st.session_state.ai_advice = ""
    st.session_state.last_plan = None


# ----------------------------- UI -----------------------------
st.title("📚 FocusFlow AI")
st.caption("Plan smarter. Adapt when life happens. Make steady progress.")

with st.sidebar:
    st.header("⚙️ Study settings")
    available_hours = st.slider("Study hours available today", 0.5, 12.0, 3.0, 0.5)
    model_name = st.text_input("Gemini Flash model", value=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                               help="Default: gemini-flash-latest. Change this only if your API account uses another supported model ID.")
    st.divider()
    st.subheader("Fixed classes / commitments")
    class_text = st.text_area("Your weekly classes", placeholder="e.g. Mon 9–11: DBMS; Tue 10–12: Python", height=100)
    st.session_state.goals = st.text_area(
        "Personal goals", value=st.session_state.goals,
        placeholder="e.g. Practice Python 20 minutes daily; sleep by 11 PM", height=100
    )
    st.caption("Your task data is kept in this browser session in this starter version. Export it before closing if needed.")

# Metrics
all_tasks = st.session_state.tasks
today = date.today()
completed_count = sum(1 for t in all_tasks if t["completed"])
pending_tasks = [t for t in all_tasks if not t["completed"]]
overdue_count = sum(1 for t in pending_tasks if date.fromisoformat(t["due_date"]) < today)
completion_rate = completed_count / len(all_tasks) if all_tasks else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total tasks", len(all_tasks))
m2.metric("Completed", completed_count)
m3.metric("Still pending", len(pending_tasks))
m4.metric("Overdue", overdue_count, delta_color="inverse")
st.progress(completion_rate, text=f"Overall completion: {completion_rate:.0%}")

# Add tasks
st.subheader("➕ Add an assignment, exam, or goal")
with st.form("add_task_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Task title", placeholder="Revise database normalization")
        subject = st.text_input("Subject / area", placeholder="DBMS")
        task_type = st.selectbox("Task type", TASK_TYPES)
    with col2:
        due_date = st.date_input("Deadline", value=today, min_value=date(2000, 1, 1))
        priority = st.select_slider("Priority", options=["Low", "Medium", "High"], value="Medium")
        estimated_hours = st.number_input("Estimated hours remaining", min_value=0.25, max_value=100.0,
                                          value=1.0, step=0.25)
    add_submitted = st.form_submit_button("Add task", type="primary", use_container_width=True)
    if add_submitted:
        if not title.strip() or not subject.strip():
            st.error("Please enter both a task title and subject / area.")
        else:
            st.session_state.tasks.append({
                "id": f"{datetime.now().timestamp()}-{len(st.session_state.tasks)}",
                "title": title.strip(),
                "subject": subject.strip(),
                "task_type": task_type,
                "due_date": due_date.isoformat(),
                "priority": priority,
                "hours": float(estimated_hours),
                "completed": False,
            })
            st.session_state.ai_advice = ""
            st.session_state.last_plan = None
            st.success("Task added. Generate a plan whenever you're ready.")

# Task management
st.subheader("🗂️ Your tasks")
if not all_tasks:
    st.info("You have no tasks yet. Add your first assignment or personal goal above.")
else:
    for task in sorted(all_tasks, key=lambda t: (t["completed"], task_sort_key(t))):
        with st.container(border=True):
            left, middle, right = st.columns([5, 1.5, 1])
            due = date.fromisoformat(task["due_date"])
            status = "Completed" if task["completed"] else ("Overdue" if due < today else "Pending")
            with left:
                st.markdown(f"**{task['title']}** — {task['subject']}")
                st.caption(f"{task['task_type']} · Due {task['due_date']} · {task['priority']} priority · {task['hours']:g}h · {status}")
            with middle:
                new_status = st.checkbox("Completed", value=task["completed"], key=f"complete_{task['id']}")
                if new_status != task["completed"]:
                    mark_task(task["id"], new_status)
                    st.rerun()
            with right:
                if st.button("Delete", key=f"delete_{task['id']}"):
                    delete_task(task["id"])
                    st.rerun()

# Analytics
if all_tasks:
    st.subheader("📈 Progress insights")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        status_df = pd.DataFrame({"Status": ["Completed", "Pending"],
                                  "Tasks": [completed_count, len(pending_tasks)]})
        fig = px.pie(status_df, names="Status", values="Tasks", hole=0.55,
                     title="Task completion")
        st.plotly_chart(fig, use_container_width=True)
    with chart_col2:
        subject_df = pd.DataFrame(all_tasks)
        subject_df["Status"] = subject_df["completed"].map({True: "Completed", False: "Pending"})
        grouped = subject_df.groupby(["subject", "Status"], as_index=False).size()
        fig = px.bar(grouped, x="subject", y="size", color="Status", barmode="stack",
                     labels={"subject": "Subject", "size": "Tasks"}, title="Tasks by subject")
        st.plotly_chart(fig, use_container_width=True)

# Planning and re-planning
st.subheader("🧠 Today's smart plan")
st.write("FocusFlow ranks pending tasks by urgency and priority, then asks Gemini Flash for coaching and a recovery plan.")
if st.button("Generate / replan my day", type="primary", use_container_width=True):
    local_plan = build_local_plan(all_tasks, available_hours, today)
    st.session_state.last_plan = local_plan
    with st.spinner("Building your plan and asking Gemini Flash for advice..."):
        st.session_state.ai_advice = generate_ai_advice(
            all_tasks, available_hours, local_plan, class_text,
            st.session_state.goals, model_name.strip() or DEFAULT_MODEL
        )

if st.session_state.last_plan:
    plan = st.session_state.last_plan
    a, b, c = st.columns(3)
    a.metric("Time available", f"{plan['available_hours']:g} h")
    b.metric("Scheduled", f"{plan['scheduled_hours']:g} h")
    c.metric("Unallocated", f"{plan['unused_hours']:g} h")
    if plan["sessions"]:
        st.markdown("**Suggested focus sessions**")
        st.dataframe(pd.DataFrame(plan["sessions"]), use_container_width=True, hide_index=True)
    else:
        st.info("No pending work to schedule. Add tasks or enjoy your free time!")
    if plan["deferred"]:
        st.warning("Some work may need another session. These tasks are not fully covered by today's available time:")
        st.write(", ".join(dict.fromkeys(t["title"] for t in plan["deferred"])))
    if st.session_state.ai_advice:
        st.markdown("### FocusFlow AI coach")
        st.markdown(st.session_state.ai_advice)

# Export
if all_tasks:
    export_df = pd.DataFrame([{k: t[k] for k in ["title", "subject", "task_type", "due_date", "priority", "hours", "completed"]}
                              for t in all_tasks])
    st.download_button("⬇️ Download tasks as CSV", export_df.to_csv(index=False).encode("utf-8"),
                       file_name="focusflow_tasks.csv", mime="text/csv")

st.divider()
st.caption("FocusFlow AI is a planning aid, not a guarantee. Review AI suggestions and adjust them to your real class schedule and energy level.")
