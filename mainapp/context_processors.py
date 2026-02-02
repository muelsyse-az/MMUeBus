from .models import Notification

def unread_notifications(request):
    """
    Makes the 'unread_count' variable available in ALL templates.
    """
    if request.user.is_authenticated:
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {'unread_count': count}
    return {'unread_count': 0}