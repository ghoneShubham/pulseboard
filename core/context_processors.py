def workspace_context(request):
    """Har template me automatically available - navbar wagairah ke liye."""
    return {
        "current_org_slug": getattr(request, "org_slug", None),
        "app_name": "PulseBoard",
    }
