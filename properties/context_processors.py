from .models import Property

def user_properties(request):
    if request.user.is_authenticated:
        return {'user_properties': Property.objects.filter(user=request.user)}
    return {}
