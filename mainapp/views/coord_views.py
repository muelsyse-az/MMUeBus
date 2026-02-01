from django.shortcuts import render

# Create your views here.
def global_map_view(request):
    return render(request, 'mainapp/common/map_view.html')