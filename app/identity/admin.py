"""Admin pages for the identity store. Emails are never shown here, only
account numbers, so the admin list can be opened on a shared screen."""

from django.contrib import admin

from .models import Account, AuditLog, ConsentRecord, ConsentVersion, Invite


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "language", "is_active", "created_at", "last_login")
    list_filter = ("role", "is_active")
    fields = ("role", "language", "is_active", "is_staff", "created_at", "last_login")
    readonly_fields = ("created_at", "last_login")


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("id", "language", "created_at", "expires_at", "used_at")
    fields = ("language", "created_at", "expires_at", "used_at")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False   # use `manage.py invite`, which also sends the email


@admin.register(ConsentVersion)
class ConsentVersionAdmin(admin.ModelAdmin):
    list_display = ("version", "language", "is_draft", "ethics_ref", "effective_from")

    def get_readonly_fields(self, request, obj=None):
        # Wording people already agreed to must never change: add a new version instead.
        if obj and ConsentRecord.objects.filter(consent_version=obj).exists():
            return [f.name for f in obj._meta.fields]
        return ()


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "purpose", "consent_version", "granted_at", "withdrawn_at")
    readonly_fields = ("account", "consent_version", "purpose", "granted_at", "withdrawn_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("at", "actor", "action", "target")
    readonly_fields = ("at", "actor", "action", "target")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
