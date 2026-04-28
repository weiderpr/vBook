from django.shortcuts import render

def help_center_view(request):
    return render(request, 'ajuda/help_center.html')
