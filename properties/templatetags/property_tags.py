from django import template
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.simple_tag(takes_context=True)
def switch_property_url(context, new_property_pk):
    request = context.get('request')
    if not request or not request.resolver_match:
        return reverse('properties:dashboard', kwargs={'pk': new_property_pk})

    rm = request.resolver_match
    view_name = rm.view_name
    kwargs = rm.kwargs.copy()

    # If it's a view that takes property_pk (like reservations or maintenance list)
    if 'property_pk' in kwargs:
        # Check if we should redirect to the list view (editing, creating, or wizard)
        should_redirect_to_list = False
        if 'pk' in kwargs:
            should_redirect_to_list = True
        elif view_name.endswith(':create') or view_name.endswith(':nova') or 'wizard' in view_name:
            should_redirect_to_list = True
            
        if should_redirect_to_list:
            # Try to go to the list of the current app
            # Use namespace from resolver_match or extract from view_name
            namespace = rm.namespace or (view_name.split(':')[0] if ':' in view_name else None)
            
            if namespace:
                try:
                    target_url = reverse(f'{namespace}:list', kwargs={'property_pk': new_property_pk})
                    return target_url
                except NoReverseMatch:
                    pass
            
            # Fallback to reservations:list (legacy behavior)
            try:
                return reverse('reservations:list', kwargs={'property_pk': new_property_pk})
            except NoReverseMatch:
                return reverse('properties:dashboard', kwargs={'pk': new_property_pk})
        
        # If it's a list view or other general view, just update property_pk
        kwargs['property_pk'] = new_property_pk
        try:
            return reverse(view_name, kwargs=kwargs)
        except NoReverseMatch:
            pass

    # If it's a property-specific view (dashboard, settings, etc.)
    if 'pk' in kwargs and (rm.app_name == 'properties' or view_name.startswith('properties:')):
        # Avoid staying on edit pages for objects that belong to the previous property
        # For properties app, pk is usually the property itself, EXCEPT for these:
        if view_name in [
            'properties:provider_update', 'properties:provider_delete', 
            'properties:cost_update', 'properties:cost_delete',
            'properties:provider_finance', 'properties:provider_add_payment'
        ]:
            return reverse('properties:dashboard', kwargs={'pk': new_property_pk})
            
        kwargs['pk'] = new_property_pk
        try:
            return reverse(view_name, kwargs=kwargs)
        except NoReverseMatch:
            pass

    # Global fallback to the dashboard of the new property
    try:
        return reverse('properties:dashboard', kwargs={'pk': new_property_pk})
    except NoReverseMatch:
        return reverse('dashboard')
