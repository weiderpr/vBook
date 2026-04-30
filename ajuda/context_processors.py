from .models import HelpPreference

def help_context(request):
    """
    Context processor to determine which help wizards should be shown to the user.
    """
    if not request.user.is_authenticated:
        return {}
        
    # List of all help tools we want to check
    help_tools = ['welcome_wizard']
    context = {}
    
    for tool in help_tools:
        # 1. Check if the user has opted out permanently in the DB
        opted_out = HelpPreference.objects.filter(
            user=request.user, 
            help_id=tool, 
            show_again=False
        ).exists()
        
        # 2. Check if the wizard has already been shown in THIS session
        session_key = f'help_{tool}_shown'
        already_shown_in_session = request.session.get(session_key, False)
        
        if not opted_out and not already_shown_in_session:
            context[f'show_{tool}'] = True
            # Mark as shown for the rest of the session
            request.session[session_key] = True
        else:
            context[f'show_{tool}'] = False
            
    return context
