from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def star_range(value):
    try:
        return range(int(round(float(value or 0))))
    except:
        return range(0)
