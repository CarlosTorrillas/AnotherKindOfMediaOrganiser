from behave import given, then


@given("the Behave test infrastructure is configured")
def step_infrastructure_is_configured(context) -> None:
    context.infrastructure_configured = True


@then("the infrastructure scenario passes")
def step_infrastructure_scenario_passes(context) -> None:
    assert context.infrastructure_configured is True

