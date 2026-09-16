from django.contrib import admin
from .models import School, Domain, Subscription


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'subdomain', 'board', 'city', 'state', 'is_active', 'created_at')
    list_filter = ('board', 'is_active', 'country', 'state')
    search_fields = ('name', 'slug', 'subdomain', 'affiliation_number', 'school_code', 'udise_code')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'school', 'is_primary', 'is_verified', 'created_at')
    list_filter = ('is_primary', 'is_verified')
    search_fields = ('domain', 'school__name')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('school', 'plan_name', 'status', 'max_students', 'start_date', 'end_date')
    list_filter = ('status', 'plan_name')
    search_fields = ('school__name', 'plan_name')
