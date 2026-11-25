from .models import Notification


def notify(recipient, title, message, kind=Notification.Kind.INFO, link=""):
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        kind=kind,
        link=link,
    )


def notify_many(recipients, title, message, kind=Notification.Kind.INFO, link=""):
    return Notification.objects.bulk_create(
        [
            Notification(
                recipient=recipient,
                title=title,
                message=message,
                kind=kind,
                link=link,
            )
            for recipient in recipients
        ]
    )
