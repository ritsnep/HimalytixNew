import re

def fix_code_generators(file_path, replacements):
    """Fix AutoIncrementCodeGenerator usage in files"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old_pattern, new_pattern in replacements:
        content = content.replace(old_pattern, new_pattern)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {file_path}')

# Fix billing
billing_replacements = [
    ("AutoIncrementCodeGenerator('PLAN', 'SubscriptionPlan', organization)", "AutoIncrementCodeGenerator(SubscriptionPlan, 'code', organization=organization, prefix='PLAN')"),
    ("AutoIncrementCodeGenerator('SUB', 'Subscription', organization)", "AutoIncrementCodeGenerator(Subscription, 'subscription_number', organization=organization, prefix='SUB')"),
    ("AutoIncrementCodeGenerator('SCHED', 'BillingSchedule', organization)", "AutoIncrementCodeGenerator(BillingSchedule, 'schedule_number', organization=organization, prefix='SCHED')"),
    ("AutoIncrementCodeGenerator('DREV', 'DeferredRevenue', organization)", "AutoIncrementCodeGenerator(DeferredRevenue, 'deferred_revenue_number', organization=organization, prefix='DREV')"),
    ("AutoIncrementCodeGenerator('USAGE', 'UsageBilling', organization)", "AutoIncrementCodeGenerator(UsageBilling, 'usage_number', organization=organization, prefix='USAGE')"),
    ("code_gen.generate()", "code_gen.generate_code()"),
]
fix_code_generators('billing/views/views_create.py', billing_replacements)

# Fix service_management
service_replacements = [
    ("AutoIncrementCodeGenerator('TKT', 'ServiceTicket', organization)", "AutoIncrementCodeGenerator(ServiceTicket, 'ticket_number', organization=organization, prefix='TKT')"),
    ("AutoIncrementCodeGenerator('SCON', 'ServiceContract', organization)", "AutoIncrementCodeGenerator(ServiceContract, 'contract_number', organization=organization, prefix='SCON')"),
    ("AutoIncrementCodeGenerator('DEV', 'DeviceLifecycle', organization)", "AutoIncrementCodeGenerator(DeviceLifecycle, 'device_number', organization=organization, prefix='DEV')"),
    ("AutoIncrementCodeGenerator('WAR', 'WarrantyTracking', organization)", "AutoIncrementCodeGenerator(WarrantyTracking, 'warranty_number', organization=organization, prefix='WAR')"),
    ("AutoIncrementCodeGenerator('HRMA', 'RMAHardware', organization)", "AutoIncrementCodeGenerator(RMAHardware, 'rma_number', organization=organization, prefix='HRMA')"),
    ("AutoIncrementCodeGenerator('SLA', 'ServiceLevel', organization)", "AutoIncrementCodeGenerator(ServiceLevel, 'code', organization=organization, prefix='SLA')"),
    ("code_gen.generate()", "code_gen.generate_code()"),
]
fix_code_generators('service_management/views/views_create.py', service_replacements)

print('All fixes complete!')
