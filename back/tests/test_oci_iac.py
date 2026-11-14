from __future__ import annotations

from pathlib import Path


STACK = Path("infra/terraform/oci")


def test_oci_stack_contains_all_deployment_layers() -> None:
    expected = {
        "autonomous_lakehouse.tf",
        "dataflow.tf",
        "guards.tf",
        "kafka.tf",
        "network.tf",
        "observability.tf",
        "outputs.tf",
        "storage.tf",
        "variables.tf",
        "versions.tf",
    }

    assert expected <= {path.name for path in STACK.glob("*.tf")}


def test_oci_paid_resources_are_opt_in() -> None:
    variables = (STACK / "variables.tf").read_text(encoding="utf-8")
    example = (STACK / "terraform.tfvars.example").read_text(encoding="utf-8")

    for variable in (
        "deployment_enabled",
        "enable_managed_kafka",
        "enable_dataflow",
        "enable_autonomous_lakehouse",
    ):
        block_start = variables.index(f'variable "{variable}"')
        block = variables[block_start : block_start + 400]
        assert "default" in block and "false" in block
        assert f"{variable} = false" in example or f"{variable}        = false" in example


def test_oci_stack_uses_vault_secret_reference_not_plain_admin_password() -> None:
    terraform_source = "\n".join(
        path.read_text(encoding="utf-8") for path in STACK.glob("*.tf")
    )

    assert "admin_password" not in terraform_source
    assert "autonomous_admin_secret_id" in terraform_source
    assert "secret_id" in terraform_source


def test_oci_topic_bootstrap_matches_project_contracts() -> None:
    script = Path("scripts/oci/create-topics.ps1").read_text(encoding="utf-8")

    for topic in (
        "entertainment.user-activity.v1",
        "entertainment.booking.v1",
        "entertainment.subscription.v1",
        "entertainment.event-attendance.v1",
        "entertainment.dead-letter.v1",
    ):
        assert topic in script
