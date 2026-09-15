"""
Custom user model. Rule #1: project ke pehle din hi custom user bana lo,
baad me swap karna migration hell hai.

AbstractUser  -> Django ka user + tumhare extra fields (easy)
AbstractBaseUser + PermissionsMixin -> full control (email login, no username)
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True
    #helper function 
    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Email required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)  # hashing yahan hoti hai, kabhi raw mat rakhna
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, is_active=True)
        return self._create(email, password, **extra)

    def active(self):
        return self.get_queryset().filter(is_active=True)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["email"]
        indexes = [models.Index(fields=["is_active", "email"], name="user_active_email_idx")]

    def __str__(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return (self.full_name or self.email).split()[0]

    def audit_label(self) -> str:  # SupportsAudit protocol satisfy karta hai
        return f"User<{self.email}>"
