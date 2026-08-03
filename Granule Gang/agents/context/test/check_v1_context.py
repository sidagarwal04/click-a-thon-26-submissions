def inspect_v1_context(context_agent):
    # Fetch the latest business-context document
    latest_context = context_agent.get_latest_context()

    print(f"=== BUSINESS CONTEXT DOCUMENT: version {latest_context['version']} ===")
    print(f"changelog: {latest_context['changelog_summary']}")
    print()
    print(latest_context["content"])

    return latest_context