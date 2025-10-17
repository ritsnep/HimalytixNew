"""
URL Configuration for i18n - Phase 3 Task 6

Routes:
- /set-language/ → Switch language
- /languages/ → List available languages
- /locale-format/ → Get locale formatting
- /user-language-preference/ → Set user preference
- /org-language-setting/ → Set org default language
- /translation-stats/ → View translation statistics
- /rtl-support/ → RTL support information
"""

from django.urls import path
from accounting.views.i18n_views import (
    LanguageSwitchView,
    LanguageListView,
    LocaleFormatView,
    UserLanguagePreferenceView,
    OrganizationLanguageSettingView,
    TranslationStatisticsView,
    RTLSupportView
)

app_name = "i18n"

urlpatterns = [
    # Language switching
    path('set-language/', 
         LanguageSwitchView.as_view(), 
         name='set_language'),
    
    # Language list
    path('languages/', 
         LanguageListView.as_view(), 
         name='languages'),
    
    # Locale formatting
    path('locale-format/', 
         LocaleFormatView.as_view(), 
         name='locale_format'),
    
    # User preference
    path('user-language-preference/', 
         UserLanguagePreferenceView.as_view(), 
         name='user_language_preference'),
    
    # Organization setting
    path('org-language-setting/', 
         OrganizationLanguageSettingView.as_view(), 
         name='org_language_setting'),
    
    # Translation statistics
    path('translation-stats/', 
         TranslationStatisticsView.as_view(), 
         name='translation_stats'),
    
    # RTL support
    path('rtl-support/', 
         RTLSupportView.as_view(), 
         name='rtl_support'),
]
