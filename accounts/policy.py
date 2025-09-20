from .models import Policy
from organizations.models import Membership

def resolve_policy(user, org_id=None):
    """Return effective Policy for a user within an organization context (if any)."""
    if org_id:
        mem = Membership.objects.filter(user=user, organization_id=org_id).select_related("organization__policy").first()
        if mem and mem.organization.policy:
            return mem.organization.policy
    return Policy.objects.first() or Policy()  # default-in-memory if none created
