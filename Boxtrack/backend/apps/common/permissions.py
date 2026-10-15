from rest_framework.permissions import BasePermission, SAFE_METHODS


def user_role(user):
    return getattr(getattr(user, 'role', None), 'name', None)


def club_is_approved(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    club = getattr(user, 'club', None)
    return bool(club and club.is_active and club.verification_status == 'APPROVED')


def scope_to_assigned_athletes(queryset, user, athlete_lookup='athlete'):
    if user_role(user) != 'TRAINER':
        return queryset
    lookup = f'{athlete_lookup}__assigned_trainer_id' if athlete_lookup else 'assigned_trainer_id'
    return queryset.filter(**{lookup: user.id})


class ClubRolePermission(BasePermission):
    allowed_roles = ()
    write_roles = None
    message = 'No tienes permisos para realizar esta operación.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        role = user_role(user)
        if role not in self.allowed_roles:
            return False
        if not club_is_approved(user) and not getattr(view, 'allow_unverified_club', False):
            return False
        if request.method in SAFE_METHODS or self.write_roles is None:
            return True
        return role in self.write_roles

    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        user = request.user
        return user.is_superuser or getattr(obj, 'club_id', None) == user.club_id


class AdminOnlyPermission(ClubRolePermission):
    allowed_roles = ('ADMIN',)
    write_roles = ('ADMIN',)


class StaffReadTrainerWritePermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER')
    write_roles = ('TRAINER',)


class StaffWritePermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER')
    write_roles = ('ADMIN', 'TRAINER')