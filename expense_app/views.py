import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Q, Sum, Min, Max
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import *




# =========================
# HOME
# =========================

def home(request):
    return render(request, "index.html")




# =========================
# LOGIN
# =========================

def login(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            auth_login(request, user)

            return redirect("welcome")

        return render(request, "login.html", {
            "error": "Invalid username or password"
        })

    return render(request, "login.html")


# =========================
# REGISTER
# =========================

def register(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:

            return render(request, "register.html", {
                "error": "Passwords do not match"
            })

        if User.objects.filter(username=username).exists():

            return render(request, "register.html", {
                "error": "Username already exists"
            })

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        return redirect("login")

    return render(request, "register.html")


# =========================
# DASHBOARD
# =========================



@login_required(login_url="login")
def welcome(request):
    user = request.user
    today = timezone.localdate()

    # =====================================
    # CURRENT MONTH DATE BOUNDARIES
    # =====================================

    current_month_start = today.replace(day=1)

    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(
            today.year,
            today.month + 1,
            1
        )

    # =====================================
    # ALL-TIME TOTALS
    # =====================================

    total_income = (
        Income.objects.filter(user=user)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    total_expense = (
        Expense.objects.filter(user=user)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    balance = total_income - total_expense

    # =====================================
    # CURRENT MONTH TOTALS
    # =====================================

    monthly_income = (
        Income.objects.filter(
            user=user,
            date__gte=current_month_start,
            date__lt=next_month_start
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    monthly_expense = (
        Expense.objects.filter(
            user=user,
            date__gte=current_month_start,
            date__lt=next_month_start
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    monthly_balance = monthly_income - monthly_expense

    # =====================================
    # FIND FIRST AND LATEST TRANSACTION DATES
    # =====================================

    first_income_date = (
        Income.objects.filter(user=user)
        .aggregate(first_date=Min("date"))["first_date"]
    )

    first_expense_date = (
        Expense.objects.filter(user=user)
        .aggregate(first_date=Min("date"))["first_date"]
    )

    latest_income_date = (
        Income.objects.filter(user=user)
        .aggregate(last_date=Max("date"))["last_date"]
    )

    latest_expense_date = (
        Expense.objects.filter(user=user)
        .aggregate(last_date=Max("date"))["last_date"]
    )

    first_dates = [
        d for d in [first_income_date, first_expense_date]
        if d is not None
    ]

    all_transaction_dates = [
        d for d in [
            first_income_date,
            first_expense_date,
            latest_income_date,
            latest_expense_date
        ]
        if d is not None
    ]

    # =====================================
    # MONTHLY SUMMARY
    # FROM FIRST TRANSACTION THROUGH LATEST
    # =====================================

    monthly_summary = []

    if first_dates:
        first_date = min(first_dates)

        # Include the current month and any future-dated transactions.
        last_date = max([today] + all_transaction_dates)

        year = first_date.year
        month_number = first_date.month

        while (year, month_number) <= (
            last_date.year,
            last_date.month
        ):
            month_start = date(year, month_number, 1)

            if month_number == 12:
                month_end = date(year + 1, 1, 1)
            else:
                month_end = date(
                    year,
                    month_number + 1,
                    1
                )

            income_total = (
                Income.objects.filter(
                    user=user,
                    date__gte=month_start,
                    date__lt=month_end
                )
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            expense_total = (
                Expense.objects.filter(
                    user=user,
                    date__gte=month_start,
                    date__lt=month_end
                )
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            monthly_summary.append({
                "month": month_start.strftime("%B %Y"),
                "income": income_total,
                "expense": expense_total,
                "balance": income_total - expense_total,
                "is_current": (
                    year == today.year
                    and month_number == today.month
                )
            })

            # Advance to the next month
            if month_number == 12:
                month_number = 1
                year += 1
            else:
                month_number += 1

    # =====================================
    # RECENT INCOME
    # =====================================

    recent_income = (
        Income.objects.filter(user=user)
        .order_by("-date", "-created_at")[:5]
    )

    # =====================================
    # RECENT EXPENSES
    # =====================================

    recent_expenses = (
        Expense.objects.filter(user=user)
        .select_related("category")
        .order_by("-date", "-id")[:5]
    )

    # =====================================
    # CHART CALCULATION
    # =====================================

    monthly_total = monthly_income + monthly_expense

    income_angle = (
        float(monthly_income / monthly_total * 360)
        if monthly_total > 0
        else 0
    )

    # =====================================
    # TEMPLATE CONTEXT
    # =====================================

    context = {
        "today": today,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "monthly_income": monthly_income,
        "monthly_expense": monthly_expense,
        "monthly_balance": monthly_balance,
        "monthly_summary": monthly_summary,
        "income_angle": income_angle,
        "recent_income": recent_income,
        "recent_expenses": recent_expenses,
    }

    return render(request, "welcome.html", context)



# =========================
# ADD CATEGORY
# =========================

@login_required(login_url="login")
def add_category(request):

    if request.method == "POST":

        name = request.POST.get("name")

        if name:

            Category.objects.create(
                user=request.user,
                name=name
            )

            return redirect("add_category")

    categories = Category.objects.filter(
        user=request.user
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "add_category.html",
        {
            "categories": categories
        }
    )


# =========================
# EDIT CATEGORY
# =========================

@login_required(login_url="login")
def edit_category(request, id):

    # Get the category belonging to the logged-in user
    category = get_object_or_404(
        Category,
        id=id,
        user=request.user
    )

    # When the form is submitted
    if request.method == "POST":

        # Get category name and remove extra spaces
        name = request.POST.get(
            "name",
            ""
        ).strip()

        # -----------------------------
        # Validate Category Name
        # -----------------------------

        if not name:

            messages.error(
                request,
                "Category name cannot be empty."
            )

            return render(
                request,
                "edit_category.html",
                {
                    "category": category
                }
            )

        # -----------------------------
        # Update Category
        # -----------------------------

        category.name = name

        category.save()

        # -----------------------------
        # Success Message
        # -----------------------------

        messages.success(
            request,
            "Category updated successfully."
        )

        # Go back to Categories page
        return redirect("add_category")

    # -----------------------------
    # GET Request
    # -----------------------------

    return render(
        request,
        "edit_category.html",
        {
            "category": category
        }
    )

# =========================
# DELETE CATEGORY
# =========================

@login_required(login_url="login")
def delete_category(request, id):

    category = get_object_or_404(
        Category,
        id=id,
        user=request.user
    )

    if request.method == "POST":

        category.delete()

    return redirect("add_category")


# =========================
# ADD INCOME
# =========================

@login_required(login_url="login")
def add_income(request):

    if request.method == "POST":

        source = request.POST.get("source", "").strip()
        amount = request.POST.get("amount", "").strip()
        date = request.POST.get("date", "").strip()
        description = request.POST.get("description", "").strip()

        # Basic validation
        if not source:
            messages.error(
                request,
                "Please enter an income source."
            )

            return redirect("add_income")

        if not amount:
            messages.error(
                request,
                "Please enter an amount."
            )

            return redirect("add_income")

        if not date:
            messages.error(
                request,
                "Please select a date."
            )

            return redirect("add_income")

        Income.objects.create(
            user=request.user,
            source=source,
            amount=amount,
            date=date,
            description=description
        )

        messages.success(
            request,
            "Income added successfully."
        )

        return redirect("add_income")


    # Latest income first
    incomes = Income.objects.filter(
        user=request.user
    ).order_by(
        "-date",
        "-created_at"
    )


    return render(
        request,
        "add_income.html",
        {
            "incomes": incomes
        }
    )


# =========================
# EDIT INCOME
# =========================

@login_required(login_url="login")
def edit_income(request, id):

    income = get_object_or_404(
        Income,
        id=id,
        user=request.user
    )


    if request.method == "POST":

        source = request.POST.get(
            "source",
            ""
        ).strip()

        amount = request.POST.get(
            "amount",
            ""
        ).strip()

        date = request.POST.get(
            "date",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()


        if not source:

            messages.error(
                request,
                "Income source cannot be empty."
            )

            return render(
                request,
                "edit_income.html",
                {
                    "income": income
                }
            )


        if not amount:

            messages.error(
                request,
                "Amount cannot be empty."
            )

            return render(
                request,
                "edit_income.html",
                {
                    "income": income
                }
            )


        if not date:

            messages.error(
                request,
                "Please select a date."
            )

            return render(
                request,
                "edit_income.html",
                {
                    "income": income
                }
            )


        income.source = source
        income.amount = amount
        income.date = date
        income.description = description

        income.save()


        messages.success(
            request,
            "Income updated successfully."
        )


        return redirect("add_income")


    return render(
        request,
        "edit_income.html",
        {
            "income": income
        }
    )



# =========================
# DELETE INCOME
# =========================

@login_required(login_url="login")
def delete_income(request, id):

    income = get_object_or_404(
        Income,
        id=id,
        user=request.user
    )


    if request.method == "POST":

        income.delete()

        messages.success(
            request,
            "Income deleted successfully."
        )


    return redirect("add_income")

# =========================
# ADD EXPENSE + FILTERS
# =========================

@login_required(login_url="login")
def add_expense(request):

    categories = Category.objects.filter(
        user=request.user
    ).order_by("name")

    # -----------------------------
    # ADD EXPENSE
    # -----------------------------

    if request.method == "POST":

        category_id = request.POST.get("category", "").strip()
        title = request.POST.get("title", "").strip()
        amount_text = request.POST.get("amount", "").strip()
        expense_date = request.POST.get("date", "").strip()
        description = request.POST.get("description", "").strip()

        # Validate title
        if not title:
            messages.error(request, "Please enter an expense title.")
            return redirect("add_expense")

        # Validate category ownership
        category = categories.filter(id=category_id).first()

        if category is None:
            messages.error(request, "Please select a valid category.")
            return redirect("add_expense")

        # Validate amount
        try:
            amount = Decimal(amount_text)

            if not amount.is_finite() or amount <= 0:
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                "Please enter a valid amount greater than zero."
            )
            return redirect("add_expense")

        # Validate date
        try:
            parsed_date = date.fromisoformat(expense_date)
        except (ValueError, TypeError):
            messages.error(request, "Please select a valid date.")
            return redirect("add_expense")

        # Save expense after validation
        Expense.objects.create(
            user=request.user,
            category=category,
            title=title,
            amount=amount,
            date=parsed_date,
            description=description
        )

        # -----------------------------
        # CHECK LOW-BALANCE EMAIL ALERT
        # -----------------------------

        profile, created = UserProfile.objects.get_or_create(
            user=request.user
        )

        total_income = Income.objects.filter(
            user=request.user
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        total_expenses = Expense.objects.filter(
            user=request.user
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        current_balance = total_income - total_expenses

        if (
            profile.spending_limit > 0
            and current_balance < profile.spending_limit
            and request.user.email
        ):
            try:
                send_mail(
                    subject="Low Balance Alert - Expense Tracker",
                    message=f"""
Hello {request.user.username},

Your current balance has fallen below your spending limit.

Spending Limit: ₹{profile.spending_limit}
Total Income: ₹{total_income}
Total Expenses: ₹{total_expenses}
Current Balance: ₹{current_balance}

Please review your expenses and manage your spending carefully.

Regards,
Expense Tracker
""",
                    from_email="snehamol825@gmail.com",
                    recipient_list=[request.user.email],
                    fail_silently=False
                )

                messages.success(
                    request,
                    "Expense added successfully and low-balance email sent."
                )

            except Exception:
                messages.warning(
                    request,
                    "Expense added successfully, but the alert email "
                    "could not be sent. Check your email configuration."
                )
        else:
            messages.success(
                request,
                "Expense added successfully."
            )

        return redirect("add_expense")

    # -----------------------------
    # EXPENSE HISTORY
    # -----------------------------

    expenses = Expense.objects.filter(
        user=request.user
    ).select_related(
        "category"
    ).order_by(
        "-date", "-id"
    )

    # -----------------------------
    # READ FILTER VALUES
    # -----------------------------

    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    category_id = request.GET.get("category", "").strip()
    min_amount = request.GET.get("min_amount", "").strip()
    max_amount = request.GET.get("max_amount", "").strip()
    search_query = request.GET.get("q", "").strip()

    # -----------------------------
    # DATE FILTERS
    # -----------------------------

    valid_start_date = None
    valid_end_date = None

    if start_date:
        try:
            valid_start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = ""
            messages.error(request, "Please enter a valid start date.")

    if end_date:
        try:
            valid_end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = ""
            messages.error(request, "Please enter a valid end date.")

    if (
        valid_start_date
        and valid_end_date
        and valid_start_date > valid_end_date
    ):
        start_date = ""
        end_date = ""
        valid_start_date = None
        valid_end_date = None

        messages.error(
            request,
            "The start date cannot be after the end date."
        )

    if valid_start_date:
        expenses = expenses.filter(date__gte=valid_start_date)

    if valid_end_date:
        expenses = expenses.filter(date__lte=valid_end_date)

    # -----------------------------
    # CATEGORY FILTER
    # -----------------------------

    selected_category = ""

    if category_id:
        category = categories.filter(id=category_id).first()

        if category:
            selected_category = str(category.id)
            expenses = expenses.filter(category=category)
        else:
            category_id = ""
            messages.error(request, "Please select a valid category.")

    # -----------------------------
    # MINIMUM AMOUNT FILTER
    # -----------------------------

    try:
        if min_amount:
            minimum = Decimal(min_amount)

            if not minimum.is_finite() or minimum < 0:
                raise InvalidOperation

            expenses = expenses.filter(amount__gte=minimum)

    except (InvalidOperation, ValueError):
        min_amount = ""
        messages.error(request, "Enter a valid minimum amount.")

    # -----------------------------
    # MAXIMUM AMOUNT FILTER
    # -----------------------------

    try:
        if max_amount:
            maximum = Decimal(max_amount)

            if not maximum.is_finite() or maximum < 0:
                raise InvalidOperation

            expenses = expenses.filter(amount__lte=maximum)

    except (InvalidOperation, ValueError):
        max_amount = ""
        messages.error(request, "Enter a valid maximum amount.")

    # Check amount range
    if min_amount and max_amount:
        try:
            if Decimal(min_amount) > Decimal(max_amount):
                min_amount = ""
                max_amount = ""
                messages.error(
                    request,
                    "Minimum amount cannot exceed maximum amount."
                )
                # Rebuild the queryset without amount filters
                expenses = Expense.objects.filter(
                    user=request.user
                ).select_related("category").order_by("-date", "-id")

                if valid_start_date:
                    expenses = expenses.filter(date__gte=valid_start_date)

                if valid_end_date:
                    expenses = expenses.filter(date__lte=valid_end_date)

                if selected_category:
                    expenses = expenses.filter(
                        category_id=selected_category
                    )

                if search_query:
                    expenses = expenses.filter(
                        Q(title__icontains=search_query)
                        | Q(description__icontains=search_query)
                    )

        except (InvalidOperation, ValueError):
            pass

    # -----------------------------
    # SEARCH TITLE / DESCRIPTION
    # -----------------------------

    if search_query:
        expenses = expenses.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # -----------------------------
    # RENDER PAGE
    # -----------------------------

    context = {
        "categories": categories,
        "expenses": expenses,
        "start_date": start_date,
        "end_date": end_date,
        "selected_category": selected_category,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "search_query": search_query,
    }

    return render(
        request,
        "add_expense.html",
        context
    )



# =========================
# EDIT EXPENSE
# =========================

@login_required(login_url="login")
def edit_expense(request, id):

    expense = get_object_or_404(
        Expense,
        id=id,
        user=request.user
    )

    categories = Category.objects.filter(
        user=request.user
    ).order_by(
        "name"
    )

    if request.method == "POST":

        category_id = request.POST.get("category")
        title = request.POST.get("title")
        amount = request.POST.get("amount")
        date = request.POST.get("date")
        description = request.POST.get("description")

        category = get_object_or_404(
            Category,
            id=category_id,
            user=request.user
        )

        expense.title = title
        expense.category = category
        expense.amount = amount
        expense.date = date
        expense.description = description

        expense.save()

        return redirect("add_expense")

    return render(
        request,
        "edit_expense.html",
        {
            "expense": expense,
            "categories": categories
        }
    )


# =========================
# DELETE EXPENSE
# =========================

@login_required(login_url="login")
def delete_expense(request, id):

    expense = get_object_or_404(
        Expense,
        id=id,
        user=request.user
    )

    if request.method == "POST":

        expense.delete()

    return redirect("add_expense")

# =========================
# SETTINGS
# =========================

@login_required(login_url="login")
def settings(request):

    profile, created = UserProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":

        email = request.POST.get("email", "").strip()
        spending_limit_text = request.POST.get(
            "spending_limit", ""
        ).strip()

        # -----------------------------
        # VALIDATE EMAIL
        # -----------------------------

        email_pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$"

        if not re.fullmatch(email_pattern, email):
            messages.error(
                request,
                "Enter a valid email address without spaces, "
                "for example snehamolkssaju@gmail.com."
            )
            return redirect("settings")

        try:
            validate_email(email)

        except ValidationError:
            messages.error(
                request,
                "Please enter a valid email address."
            )
            return redirect("settings")

        # -----------------------------
        # VALIDATE SPENDING LIMIT
        # -----------------------------

        try:
            spending_limit = Decimal(spending_limit_text)

            if (
                not spending_limit.is_finite()
                or spending_limit < 0
            ):
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                "Enter a valid, non-negative spending limit."
            )
            return redirect("settings")

        # -----------------------------
        # SAVE SETTINGS AFTER VALIDATION
        # -----------------------------

        request.user.email = email
        request.user.save(update_fields=["email"])

        profile.spending_limit = spending_limit
        profile.save(update_fields=["spending_limit"])

        # -----------------------------
        # SUCCESS MESSAGE
        # -----------------------------

        messages.success(
            request,
            "Settings updated successfully."
        )

        return redirect("settings")

    # -----------------------------
    # DISPLAY SETTINGS PAGE
    # -----------------------------

    return render(
        request,
        "settings.html",
        {
            "profile": profile
        }
    )




# =========================
# LOGOUT
# =========================

def user_logout(request):


    logout(request)

    return redirect("home")