"""Pure config -> desired-state mapping (no network / auth / mutation)."""

from __future__ import annotations

from purview_governance.config.models import (
    ClassificationRuleResourceConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    ScanResourceConfig,
    ScanRuleSetResourceConfig,
)
from purview_governance.desired.models import (
    ClassificationRuleDesiredState,
    DataSourceDesiredState,
    DesiredState,
    RegexClassificationPatternDesired,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)


def desired_state_from_config(config: GovernanceConfig) -> DesiredState:
    """Map normalized governance config to comparison desired state."""
    data_sources = tuple(
        DataSourceDesiredState(
            name=resource.name,
            kind="AzureStorage",
            endpoint=resource.endpoint,
            collection_reference_name=resource.collection_reference_name,
        )
        for resource in config.resources
        if isinstance(resource, DataSourceResourceConfig)
    )
    classification_rules = tuple(
        ClassificationRuleDesiredState(
            name=resource.name,
            kind="Custom",
            classification_name=resource.classification_name,
            minimum_percentage_match=resource.minimum_percentage_match,
            rule_status=resource.rule_status,
            data_patterns=tuple(
                RegexClassificationPatternDesired(pattern=item.pattern)
                for item in resource.data_patterns
            ),
            column_patterns=tuple(
                RegexClassificationPatternDesired(pattern=item.pattern)
                for item in resource.column_patterns
            ),
            description=resource.description,
        )
        for resource in config.resources
        if isinstance(resource, ClassificationRuleResourceConfig)
    )
    scan_rule_sets = tuple(
        ScanRuleSetDesiredState(
            name=resource.name,
            kind="AzureStorage",
            scan_ruleset_type="Custom",
            file_extensions=resource.file_extensions,
            excluded_system_classifications=resource.excluded_system_classifications,
            included_custom_classification_rule_names=(
                resource.included_custom_classification_rule_names
            ),
            description=resource.description,
        )
        for resource in config.resources
        if isinstance(resource, ScanRuleSetResourceConfig)
    )
    scans = tuple(
        ScanDesiredState(
            name=resource.name,
            kind="AzureStorageMsi",
            data_source_name=resource.data_source_name,
            scan_ruleset_name=resource.scan_ruleset_name,
            scan_ruleset_type=resource.scan_ruleset_type,
            collection_reference_name=resource.collection_reference_name,
        )
        for resource in config.resources
        if isinstance(resource, ScanResourceConfig)
    )
    return DesiredState(
        data_sources=tuple(sorted(data_sources, key=lambda item: item.name)),
        classification_rules=tuple(sorted(classification_rules, key=lambda item: item.name)),
        scan_rule_sets=tuple(sorted(scan_rule_sets, key=lambda item: item.name)),
        scans=tuple(sorted(scans, key=lambda item: (item.data_source_name, item.name))),
    )
