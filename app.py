import streamlit as st
import json
import os
import calendar
import uuid
import hashlib
import matplotlib.pyplot as plt
from datetime import date, timedelta

CATEGORY_ICONS = {
    "food": "🍔",
    "clothes": "👕",
    "entertainment": "🎬",
    "savings": "💰",
    "other": "📦",
    "N/A": "💵"
}

def icon_for(category):
    return CATEGORY_ICONS.get(category, "💵")

# Historical U.S. stock market average annual return is often cited around 7% after inflation.
# This is illustrative, not a guarantee -- real returns vary a lot year to year.
AVG_MARKET_RETURN = 0.07

def future_value(amount, years, rate=AVG_MARKET_RETURN):
    return amount * ((1 + rate) ** years)

def hash_password(password):
    """Turn a password into a scrambled, one-way string. The real password is never stored."""
    return hashlib.sha256(password.encode()).hexdigest()

st.set_page_config(page_title="Teen Budget Tracker", layout="centered")

# ---------------- USERNAME / PASSWORD ----------------
USERS_FILENAME = "users.json"
if os.path.exists(USERS_FILENAME):
    with open(USERS_FILENAME, "r") as f:
        all_users = json.load(f)
else:
    all_users = {}

st.sidebar.subheader("👤 Your Profile")
raw_username = st.sidebar.text_input("Username", value=st.session_state.get("username_input", ""))
raw_password = st.sidebar.text_input("Password", type="password")
st.session_state.username_input = raw_username

username = "".join(c for c in raw_username.strip().lower().replace(" ", "_") if c.isalnum() or c == "_")

if not username or not raw_password:
    st.title("💰 Teen Budget Tracker")
    st.info("👈 Enter a username and password in the sidebar. First time here? Just make one up — it'll create your account automatically.")
    st.stop()

if username not in all_users:
    # First time seeing this username -- create the account right now
    all_users[username] = hash_password(raw_password)
    with open(USERS_FILENAME, "w") as f:
        json.dump(all_users, f, indent=2)
    st.sidebar.success("Account created!")
else:
    if hash_password(raw_password) != all_users[username]:
        st.title("💰 Teen Budget Tracker")
        st.error("Incorrect password for that username.")
        st.stop()

FILENAME = f"transactions_{username}.json"
GOALS_FILENAME = f"goals_{username}.json"
REMINDERS_FILENAME = f"reminders_{username}.json"

# Reload data whenever the username changes (including the very first load)
if st.session_state.get("loaded_username") != username:
    if os.path.exists(FILENAME):
        with open(FILENAME, "r") as f:
            loaded = json.load(f)
    else:
        loaded = []
    for t in loaded:
        if "date" not in t:
            t["date"] = date.today().isoformat()
        if "id" not in t:
            t["id"] = uuid.uuid4().hex
    st.session_state.transactions = loaded

    if os.path.exists(GOALS_FILENAME):
        with open(GOALS_FILENAME, "r") as f:
            st.session_state.goals = json.load(f)
    else:
        st.session_state.goals = []

    if os.path.exists(REMINDERS_FILENAME):
        with open(REMINDERS_FILENAME, "r") as f:
            st.session_state.reminders = json.load(f)
    else:
        st.session_state.reminders = []

    st.session_state.loaded_username = username
    st.session_state.month_offset = 0

def save_goals():
    with open(GOALS_FILENAME, "w") as f:
        json.dump(st.session_state.goals, f, indent=2)

def save_reminders():
    with open(REMINDERS_FILENAME, "w") as f:
        json.dump(st.session_state.reminders, f, indent=2)

st.sidebar.caption(f"Signed in as **{username}**")
st.title("💰 Teen Budget Tracker")

# ---------------- REMINDERS BANNER ----------------
today_for_reminders = date.today()
upcoming_soon = [
    r for r in st.session_state.reminders
    if 0 <= (date.fromisoformat(r["due_date"]) - today_for_reminders).days <= 7
]
if upcoming_soon:
    for r in sorted(upcoming_soon, key=lambda r: r["due_date"]):
        days_left = (date.fromisoformat(r["due_date"]) - today_for_reminders).days
        when = "today" if days_left == 0 else f"in {days_left} day(s)"
        st.warning(rf"🔔 **{r['name']}** — \${r['amount']:.2f} due {when} ({r['due_date']})")

# ---------------- ADD TRANSACTION ----------------
st.subheader("Add a transaction")

col1, col2 = st.columns(2)
with col1:
    entry_type = st.selectbox("Type", ["income", "expense"])
    amount = st.number_input("Amount ($)", min_value=0.0, step=1.0)
with col2:
    entry_date = st.date_input("Date", value=date.today())
    category = "N/A"
    goal_for_this_entry = None
    if entry_type == "expense":
        category = st.selectbox("Category", ["food", "clothes", "entertainment", "savings", "other"],
                                  format_func=lambda c: f"{icon_for(c)} {c}")
        if category == "savings" and st.session_state.goals:
            goal_names = [g["name"] for g in st.session_state.goals]
            goal_for_this_entry = st.selectbox("Which goal is this for?", goal_names)

if st.button("Add Transaction"):
    st.session_state.transactions.append({
        "id": uuid.uuid4().hex,
        "amount": amount,
        "type": entry_type,
        "category": category,
        "date": entry_date.isoformat(),
        "goal": goal_for_this_entry
    })
    with open(FILENAME, "w") as f:
        json.dump(st.session_state.transactions, f, indent=2)
    st.success("Added!")
    if entry_type == "expense" and category != "savings" and amount > 0:
        fv = future_value(amount, 10)
        st.info(rf"💡 If you'd invested this \${amount:.2f} instead, at a historical ~7%/year average market return, it could be worth about **\${fv:.2f}** in 10 years.")

# ---------------- FILTER ----------------
st.subheader("View")
time_range = st.radio("Show:", ["Week", "Month", "Year", "All Time"], horizontal=True)

today = date.today()
if time_range == "Week":
    start = today - timedelta(days=today.weekday())
elif time_range == "Month":
    start = today.replace(day=1)
elif time_range == "Year":
    start = today.replace(month=1, day=1)
else:
    start = date.min

filtered = [
    t for t in st.session_state.transactions
    if date.fromisoformat(t["date"]) >= start
]

# ---------------- BALANCE ----------------
balance = 0
for t in filtered:
    if t["type"] == "income":
        balance += t["amount"]
    else:
        balance -= t["amount"]

st.metric(f"Balance ({time_range})", f"${balance:.2f}")

# ---------------- CATEGORY BREAKDOWN ----------------
totals_by_category = {}
for t in filtered:
    if t["type"] == "expense":
        cat = t["category"]
        totals_by_category[cat] = totals_by_category.get(cat, 0) + t["amount"]

if totals_by_category:
    st.subheader("Spending by category")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.bar_chart(totals_by_category)
    with chart_col2:
        labels = list(totals_by_category.keys())
        fig, ax = plt.subplots()
        ax.pie(totals_by_category.values(), labels=labels, autopct="%1.0f%%", startangle=90)
        ax.axis("equal")
        st.pyplot(fig)

# ---------------- CALENDAR HEATMAP ----------------
st.subheader("Calendar view")

nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
with nav_col1:
    if st.button("← Prev"):
        st.session_state.month_offset -= 1
with nav_col3:
    if st.button("Next →"):
        st.session_state.month_offset += 1

# Figure out which year/month we're viewing based on the offset
view_month_index = today.month - 1 + st.session_state.month_offset
view_year = today.year + view_month_index // 12
view_month = view_month_index % 12 + 1

with nav_col2:
    st.markdown(f"<h4 style='text-align:center'>{calendar.month_name[view_month]} {view_year}</h4>", unsafe_allow_html=True)

# Total expenses per day-of-month for the viewed month
daily_totals = {}
for t in st.session_state.transactions:
    if t["type"] == "expense":
        d = date.fromisoformat(t["date"])
        if d.year == view_year and d.month == view_month:
            daily_totals[d.day] = daily_totals.get(d.day, 0) + t["amount"]

max_total = max(daily_totals.values()) if daily_totals else 0

weekday_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
header_cols = st.columns(7)
for c, name in zip(header_cols, weekday_headers):
    c.markdown(f"<div style='text-align:center;font-size:11px;color:gray'>{name}</div>", unsafe_allow_html=True)

weeks = calendar.monthcalendar(view_year, view_month)
for week in weeks:
    row = st.columns(7)
    for col, day in zip(row, week):
        if day == 0:
            col.markdown("&nbsp;", unsafe_allow_html=True)
            continue
        spent = daily_totals.get(day, 0)
        intensity = (spent / max_total) if max_total > 0 else 0
        alpha = 0.12 + 0.7 * intensity if spent > 0 else 0.04
        is_today = (day == today.day and view_month == today.month and view_year == today.year)
        border = "2px solid #333" if is_today else "1px solid #ddd"
        col.markdown(
            f"""<div style='background:rgba(200,50,50,{alpha});border:{border};
            border-radius:6px;padding:6px 2px;text-align:center;margin-bottom:4px'>
            <div style='font-size:12px;font-weight:600'>{day}</div>
            <div style='font-size:10px;color:#555'>{'$'+format(spent, '.0f') if spent else ''}</div>
            </div>""",
            unsafe_allow_html=True
        )

# ---------------- GOALS ----------------
st.subheader("🎯 Savings Goals")

with st.form("new_goal_form", clear_on_submit=True):
    st.markdown("**Add a new goal**")
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        new_goal_name = st.text_input("Goal name (e.g. New phone)")
    with g_col2:
        new_goal_target = st.number_input("Target amount ($)", min_value=0.0, step=10.0)
    goal_submitted = st.form_submit_button("Add Goal")
    if goal_submitted and new_goal_name.strip():
        st.session_state.goals.append({"name": new_goal_name.strip(), "target": new_goal_target})
        save_goals()
        st.success(f"Goal '{new_goal_name}' added!")

if st.session_state.goals:
    for g in st.session_state.goals:
        saved_so_far = sum(
            t["amount"] for t in st.session_state.transactions
            if t["type"] == "expense" and t["category"] == "savings" and t.get("goal") == g["name"]
        )
        progress = min(saved_so_far / g["target"], 1.0) if g["target"] > 0 else 0
        st.markdown(rf"**{g['name']}** — \${saved_so_far:.2f} of \${g['target']:.2f}")
        st.progress(progress)
else:
    st.caption("No goals yet — add one above, then pick it whenever you log a savings transaction.")

# ---------------- MONEY VS. TIME ----------------
st.subheader("📈 Money vs. Time")

non_savings_expenses_total = sum(
    t["amount"] for t in filtered
    if t["type"] == "expense" and t["category"] != "savings"
)

if non_savings_expenses_total > 0:
    st.markdown(rf"You've spent **\${non_savings_expenses_total:.2f}** on non-savings expenses ({time_range.lower()}). Here's what that same money could look like if it had been invested instead:")
    mvt_col1, mvt_col2, mvt_col3 = st.columns(3)
    with mvt_col1:
        st.metric("In 5 years", f"${future_value(non_savings_expenses_total, 5):,.2f}")
    with mvt_col2:
        st.metric("In 10 years", f"${future_value(non_savings_expenses_total, 10):,.2f}")
    with mvt_col3:
        st.metric("In 20 years", f"${future_value(non_savings_expenses_total, 20):,.2f}")
    st.caption("Based on a historical ~7%/year average U.S. stock market return. This is illustrative, not a guarantee — real returns vary and can go down as well as up.")
else:
    st.caption("Log some expenses and I'll show you what that money could be worth if invested instead.")

# ---------------- SPENDING PACE ----------------
st.subheader("📊 Spending Pace")

days_in_month = calendar.monthrange(today.year, today.month)[1]
days_elapsed = today.day

month_expenses = [
    t for t in st.session_state.transactions
    if t["type"] == "expense"
    and date.fromisoformat(t["date"]).year == today.year
    and date.fromisoformat(t["date"]).month == today.month
]
total_spent_this_month = sum(t["amount"] for t in month_expenses)
daily_avg = total_spent_this_month / days_elapsed if days_elapsed > 0 else 0
projected_total = daily_avg * days_in_month

month_income = sum(
    t["amount"] for t in st.session_state.transactions
    if t["type"] == "income"
    and date.fromisoformat(t["date"]).year == today.year
    and date.fromisoformat(t["date"]).month == today.month
)

pace_col1, pace_col2, pace_col3 = st.columns(3)
with pace_col1:
    st.metric("Spent so far this month", f"${total_spent_this_month:.2f}")
with pace_col2:
    st.metric("Daily average", f"${daily_avg:.2f}")
with pace_col3:
    st.metric(f"Projected by day {days_in_month}", f"${projected_total:.2f}")

st.caption(f"Day {days_elapsed} of {days_in_month} this month.")

if month_income > 0:
    if projected_total > month_income:
        st.warning(rf"At this pace, you're projected to spend \${projected_total - month_income:.2f} more than you've earned this month (\${month_income:.2f}).")
    else:
        st.success(rf"At this pace, you're on track to stay within this month's income (\${month_income:.2f}).")

# ---------------- REMINDERS MANAGER ----------------
st.subheader("🔔 Upcoming Payments")

with st.form("new_reminder_form", clear_on_submit=True):
    st.markdown("**Add an upcoming payment**")
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
        new_reminder_name = st.text_input("What is it? (e.g. Phone bill)")
    with r_col2:
        new_reminder_amount = st.number_input("Amount ($)", min_value=0.0, step=1.0, key="reminder_amount")
    with r_col3:
        new_reminder_date = st.date_input("Due date", value=date.today(), key="reminder_date")
    reminder_submitted = st.form_submit_button("Add Reminder")
    if reminder_submitted and new_reminder_name.strip():
        st.session_state.reminders.append({
            "name": new_reminder_name.strip(),
            "amount": new_reminder_amount,
            "due_date": new_reminder_date.isoformat()
        })
        save_reminders()
        st.success(f"Reminder '{new_reminder_name}' added!")

upcoming_all = sorted(st.session_state.reminders, key=lambda r: r["due_date"])
if upcoming_all:
    for r in upcoming_all:
        st.markdown(rf"- **{r['name']}** — \${r['amount']:.2f} due {r['due_date']}")
else:
    st.caption("No upcoming payments logged yet.")

# ---------------- BUDGET ASSISTANT (rule-based, no API needed) ----------------
st.subheader("💡 Budget Assistant")

this_week_start = today - timedelta(days=today.weekday())
last_week_start = this_week_start - timedelta(days=7)
last_week_end = this_week_start - timedelta(days=1)

this_week_expenses = sum(
    t["amount"] for t in st.session_state.transactions
    if t["type"] == "expense" and this_week_start <= date.fromisoformat(t["date"]) <= today
)
last_week_expenses = sum(
    t["amount"] for t in st.session_state.transactions
    if t["type"] == "expense" and last_week_start <= date.fromisoformat(t["date"]) <= last_week_end
)

monthly_txns = [
    t for t in st.session_state.transactions
    if date.fromisoformat(t["date"]).year == today.year and date.fromisoformat(t["date"]).month == today.month
]
monthly_category_totals = {}
for t in monthly_txns:
    if t["type"] == "expense":
        monthly_category_totals[t["category"]] = monthly_category_totals.get(t["category"], 0) + t["amount"]

top_category = max(monthly_category_totals, key=monthly_category_totals.get) if monthly_category_totals else None
has_savings_this_month = any(t["category"] == "savings" for t in monthly_txns)

CATEGORY_TIPS = {
    "food": "Try meal-prepping or setting a weekly food budget to cut down on impulse buys.",
    "clothes": "A 24-hour rule before non-essential clothing purchases can cut impulse spending a lot.",
    "entertainment": "Check for free or student-discounted versions of subscriptions you're paying for.",
    "other": "Try splitting 'other' into more specific categories next time — it'll show patterns you're missing.",
    "savings": "Nice — keep treating savings like a regular expense, not what's left over."
}

insights = []
if top_category:
    insights.append(rf"Your biggest expense category this month is **{top_category}** (\${monthly_category_totals[top_category]:.2f}). {CATEGORY_TIPS.get(top_category, '')}")
if last_week_expenses > 0:
    pct_change = ((this_week_expenses - last_week_expenses) / last_week_expenses) * 100
    if pct_change > 5:
        insights.append(rf"You've spent {pct_change:.0f}% more this week (\${this_week_expenses:.2f}) than last week (\${last_week_expenses:.2f}).")
    elif pct_change < -5:
        insights.append(rf"You've spent {abs(pct_change):.0f}% less this week (\${this_week_expenses:.2f}) than last week (\${last_week_expenses:.2f}) — nice.")
    else:
        insights.append(rf"Your spending this week (\${this_week_expenses:.2f}) is about the same as last week.")
if not has_savings_this_month:
    insights.append("You haven't logged any savings this month — even a small, regular amount adds up over time.")

if insights:
    for i in insights:
        st.markdown(f"- {i}")
else:
    st.caption("Log a few transactions and I'll start showing you real patterns.")

st.markdown("**Ask a question:**")
user_question = st.text_input("e.g. \"where can I cut back?\" or \"how am I doing?\"", key="assistant_question")
if st.button("Ask"):
    q = user_question.lower()
    if "cut back" in q or "reduce" in q or "spend less" in q:
        if top_category:
            response = rf"Your biggest expense category this month is {top_category}, at \${monthly_category_totals[top_category]:.2f}. {CATEGORY_TIPS.get(top_category, '')}"
        else:
            response = "Log a few more expenses first so I can see where your money's actually going."
    elif "doing" in q or "summary" in q or "how am i" in q:
        response = rf"This month you've spent \${sum(monthly_category_totals.values()):.2f} across {len(monthly_category_totals)} categories. Your current balance ({time_range}) is \${balance:.2f}."
    elif "sav" in q:
        if has_savings_this_month:
            response = "You've already logged savings this month — keep it up."
        else:
            response = "You haven't logged any savings yet this month. Even $5 a week adds up over a year."
    elif "week" in q:
        if last_week_expenses > 0:
            response = rf"This week: \${this_week_expenses:.2f}. Last week: \${last_week_expenses:.2f}."
        else:
            response = "I don't have last week's data yet to compare against."
    else:
        response = "Try asking things like: 'where can I cut back?', 'how am I doing?', or 'should I save more?'"
    st.info(response)

# ---------------- EDIT OR DELETE A TRANSACTION ----------------
st.subheader("✏️ Edit or Delete a Transaction")

if st.session_state.transactions:
    sorted_txns = sorted(st.session_state.transactions, key=lambda t: t["date"], reverse=True)
    options = [t["id"] for t in sorted_txns]
    label_lookup = {
        t["id"]: f"{t['date']} — {icon_for(t['category'])} {t['category']} — {t['type']} — ${t['amount']:.2f}"
        for t in sorted_txns
    }
    selected_id = st.selectbox(
        "Select a transaction",
        options,
        format_func=lambda i: label_lookup[i]
    )
    selected_txn = next(t for t in st.session_state.transactions if t["id"] == selected_id)

    edit_col1, edit_col2 = st.columns(2)
    with edit_col1:
        edit_type = st.selectbox("Type", ["income", "expense"],
                                   index=0 if selected_txn["type"] == "income" else 1,
                                   key="edit_type")
        edit_amount = st.number_input("Amount ($)", min_value=0.0, step=1.0,
                                        value=float(selected_txn["amount"]), key="edit_amount")
    with edit_col2:
        edit_date = st.date_input("Date", value=date.fromisoformat(selected_txn["date"]), key="edit_date")
        edit_category = selected_txn["category"]
        if edit_type == "expense":
            cat_options = ["food", "clothes", "entertainment", "savings", "other"]
            cat_index = cat_options.index(selected_txn["category"]) if selected_txn["category"] in cat_options else 0
            edit_category = st.selectbox("Category", cat_options, index=cat_index,
                                          format_func=lambda c: f"{icon_for(c)} {c}", key="edit_category")
        else:
            edit_category = "N/A"

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Update Transaction"):
            selected_txn["type"] = edit_type
            selected_txn["amount"] = edit_amount
            selected_txn["date"] = edit_date.isoformat()
            selected_txn["category"] = edit_category
            with open(FILENAME, "w") as f:
                json.dump(st.session_state.transactions, f, indent=2)
            st.success("Updated!")
            st.rerun()
    with btn_col2:
        if st.button("Delete Transaction", type="secondary"):
            st.session_state.transactions = [
                t for t in st.session_state.transactions if t["id"] != selected_id
            ]
            with open(FILENAME, "w") as f:
                json.dump(st.session_state.transactions, f, indent=2)
            st.success("Deleted.")
            st.rerun()
else:
    st.caption("No transactions yet to edit or delete.")

# ---------------- FULL LIST ----------------
st.subheader("All transactions")
display_rows = []
for t in sorted(filtered, key=lambda t: t["date"], reverse=True):
    display_rows.append({
        "date": t["date"],
        "type": t["type"],
        "category": f"{icon_for(t['category'])} {t['category']}",
        "amount": f"${t['amount']:.2f}"
    })
st.table(display_rows)
