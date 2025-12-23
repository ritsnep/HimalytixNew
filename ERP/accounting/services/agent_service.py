from accounting.models import Vendor, Agent, Area
from django.core.exceptions import ValidationError


class AgentService:
    """
    Service for managing agents and areas, including auto-selection logic.
    """

    @staticmethod
    def get_agents_for_dropdown(organization):
        """
        Get active agents for dropdown selection filtered by organization.
        """
        agents = Agent.objects.filter(organization=organization, is_active=True).order_by('name')
        return [
            {'id': agent.id, 'name': f"{agent.code} - {agent.name}"}
            for agent in agents
        ]

    @staticmethod
    def get_areas_for_dropdown(organization):
        """
        Get active areas for dropdown selection filtered by organization.
        """
        areas = Area.objects.filter(organization=organization, is_active=True).order_by('name')
        return [
            {'id': area.area_id, 'name': f"{area.code} - {area.name}"}
            for area in areas
        ]

    @staticmethod
    def auto_select_agent_for_vendor(organization, vendor_id):
        """
        Auto-select agent and area based on vendor's location or default settings.
        Currently uses simple logic - can be enhanced with more complex rules.
        """
        try:
            vendor = Vendor.objects.get(organization=organization, vendor_id=vendor_id)

            # Try to find agent by area if vendor has address info
            # For now, use default agent/area or first active ones
            agent = Agent.objects.filter(organization=organization, is_active=True).order_by('name').first()
            area = Area.objects.filter(organization=organization, is_active=True).order_by('name').first()

            return {
                'agent_id': agent.pk if agent else None,
                'area_id': area.area_id if area else None,
                'agent_name': agent.name if agent else None,
                'area_name': area.name if area else None,
            }
        except Vendor.DoesNotExist:
            return {'agent_id': None, 'area_id': None, 'agent_name': None, 'area_name': None}

    @staticmethod
    def get_agent_details(agent_id):
        """
        Get detailed information about a specific agent.
        """
        try:
            agent = Agent.objects.get(pk=agent_id, is_active=True)
            return {
                'id': agent.pk,
                'code': agent.code,
                'name': agent.name,
                'area': agent.area,
                'phone': agent.phone,
                'email': agent.email,
                'commission_rate': agent.commission_rate,
            }
        except Agent.DoesNotExist:
            raise ValidationError(f"Agent with ID {agent_id} does not exist or is inactive.")

    @staticmethod
    def get_area_details(area_id):
        """
        Get detailed information about a specific area.
        """
        try:
            area = Area.objects.get(area_id=area_id, is_active=True)
            return {
                'id': area.area_id,
                'code': area.code,
                'name': area.name,
                'description': area.description,
                'region': area.region,
            }
        except Area.DoesNotExist:
            raise ValidationError(f"Area with ID {area_id} does not exist or is inactive.")

    @staticmethod
    def get_agent_details(agent_id):
        """
        Get detailed agent information.
        Placeholder implementation.
        """
        # Placeholder data
        agents = {
            1: {'id': 1, 'name': 'Agent Ram', 'phone': '123-456-7890', 'email': 'ram@example.com', 'area': 'Birgunj', 'commission_rate': 5.0, 'is_active': True},
            2: {'id': 2, 'name': 'Agent Shyam', 'phone': '098-765-4321', 'email': 'shyam@example.com', 'area': 'Parsa', 'commission_rate': 4.5, 'is_active': True},
        }
        return agents.get(agent_id, {})

    @staticmethod
    def assign_agent_to_vendor(vendor_id, agent_id):
        """
        Assign an agent to a vendor.
        Placeholder implementation.
        """
        # In production: vendor.default_agent = agent; vendor.save()
        pass

    @staticmethod
    def get_agents_by_area(area_id):
        """
        Get all agents for a specific area.
        Placeholder implementation.
        """
        # Placeholder logic
        return [
            {'id': 1, 'name': 'Agent Ram'},
        ]

    @staticmethod
    def validate_agent_assignment(vendor_id, agent_id):
        """
        Validate if agent can be assigned to vendor (e.g., area compatibility).
        Placeholder implementation.
        """
        # Placeholder validation
        return {'valid': True, 'message': 'OK'}
