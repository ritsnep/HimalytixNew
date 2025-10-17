from ..models import ChartOfAccount

class SuggestionService:
    """
    A service to provide suggestions for journal entry lines.
    """

    def get_suggestions(self, description_text: str) -> list:
        """
        Get suggestions based on the description text.

        For now, this is a simple rule-based engine.
        """
        if not description_text:
            return []

        # Suggest accounts that have a name containing the description text
        accounts = ChartOfAccount.objects.filter(account_name__icontains=description_text)[:5]
        
        suggestions = [
            {
                "account_id": account.id,
                "account_name": account.name,
                "account_code": account.code,
            }
            for account in accounts
        ]

        return suggestions