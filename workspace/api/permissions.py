from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.enums import Role

from ..models import Membership


class IsOrgMember(BasePermission):
    """
    has_permission      -> view-level (list/create)
    has_object_permission -> object-level (retrieve/update/delete)
    Dono chahiye. Sirf object-level likhoge toh list endpoint khula reh jaayega.
    """

    message = "You do not have access to this organization."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        organization_id = getattr(obj, "organization_id", None) or obj.project.organization_id
        membership = Membership.objects.filter(
            user=request.user, organization_id=organization_id
        ).first()
        if membership is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return Role(membership.role).can_manage
