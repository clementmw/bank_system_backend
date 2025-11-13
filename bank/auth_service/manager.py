from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ObjectDoesNotExist

class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
        from .models import Role   # Lazy import (prevents circular import)

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        try:
            admin_role = Role.objects.get(name="ADMIN")
        except ObjectDoesNotExist:
            admin_role = Role.objects.create(name="ADMIN")
        extra_fields.setdefault("role", admin_role)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
