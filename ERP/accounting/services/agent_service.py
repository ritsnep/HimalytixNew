from accounting.models import Vendor, Agent
from locations.models import LocationNode
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
    def get_areas_for_dropdown(organization=None):
        """
        Get active areas for dropdown selection. The organization argument is accepted for
        future filtering needs even though areas are currently organization-agnostic.
        """
        areas = LocationNode.objects.filter(type=LocationNode.Type.AREA, is_active=True).order_by('name_en')
        return [
            {'id': area.id, 'name': f"{area.name_en}"}
            for area in areas
        ]

    @staticmethod
    def auto_select_agent_for_vendor(organization, vendor_id):
        """
        Auto-select agent and area based on vendor's stored assignments or location.
        First checks if vendor has assigned agent/area, then matches by area, else defaults.
        """
        try:
            vendor = Vendor.objects.get(organization=organization, vendor_id=vendor_id)

            # First, check if vendor has stored agent and area
            if vendor.agent and vendor.area:
                return {
                    'agent_id': vendor.agent.pk,
                    'area_id': vendor.area.id,
                    'agent_name': vendor.agent.name,
                    'area_name': vendor.area.name_en,
                }

            # If vendor has area but no agent, find agent for that area
            if vendor.area:
                agent = Agent.objects.filter(
                    organization=organization,
                    is_active=True,
                    area=vendor.area
                ).order_by('name').first()
                if agent:
                    return {
                        'agent_id': agent.pk,
                        'area_id': vendor.area.id,
                        'agent_name': agent.name,
                        'area_name': vendor.area.name_en,
                    }

            # Fallback: first active agent and its area, or first area
            agent = Agent.objects.filter(organization=organization, is_active=True).order_by('name').first()
            if agent and agent.area:
                return {
                    'agent_id': agent.pk,
                    'area_id': agent.area.id,
                    'agent_name': agent.name,
                    'area_name': agent.area.name_en,
                }
            else:
                area = LocationNode.objects.filter(type=LocationNode.Type.AREA, is_active=True).order_by('name_en').first()
                return {
                    'agent_id': agent.pk if agent else None,
                    'area_id': area.id if area else None,
                    'agent_name': agent.name if agent else None,
                    'area_name': area.name_en if area else None,
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
