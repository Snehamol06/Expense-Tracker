from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login, name="login"),
    path('register/',views.register,name="register"),
    path('welcome/',views.welcome,name="welcome"),
    path("logout/", views.user_logout, name="user_logout"),
    path("add_category/", views.add_category, name="add_category"),
    path('edit_category/<int:id>/',views.edit_category,name="edit_category"),
    path('delete_category/<int:id>/',views.delete_category,name="delete_category"),
    path("add_expense/", views.add_expense, name="add_expense"),
    path('edit_expense/<int:id>/',views.edit_expense,name="edit_expense"),
    path('delete_expense/<int:id>/',views.delete_expense,name="delete_expense"),
    path("add_income/", views.add_income, name="add_income"),
    path('edit_income/<int:id>/',views.edit_income,name="edit_income"),
    path('delete_income/<int:id>/',views.delete_income,name="delete_income"),
    path("settings/", views.settings, name="settings"),
]