from django.contrib import admin
from .models import COTPosition, COTReport, DataSource, SyncRun
admin.site.register(DataSource)
admin.site.register(SyncRun)
admin.site.register(COTReport)
admin.site.register(COTPosition)
