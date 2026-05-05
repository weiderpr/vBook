def is_mobile(request):
    """
    Detects if the request comes from a mobile device based on the User-Agent header
    or if the request is targeting a mobile-specific path.
    """
    # Check if it's a mobile-specific path (including with the /book/ prefix)
    current_path = request.path
    if '/mobile/' in current_path:
        return True

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_patterns = [
        'iphone', 'android', 'phone', 'mobile', 'mobi', 'webos', 'ipod', 'blackberry',
        'windows phone', 'iemobile', 'opera mini', 'standalone'
    ]
    return any(pattern in user_agent for pattern in mobile_patterns)
