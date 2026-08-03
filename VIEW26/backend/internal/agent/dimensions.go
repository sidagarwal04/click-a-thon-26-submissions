package agent

import (
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

// dimensionDefinition is the semantic allow-list that turns physical fields
// into governed analytical dimensions. A field appearing in a table is not by
// itself enough to make it safe for business questions: the context layer also
// records what the field means and the aliases that may resolve to it.
type dimensionDefinition struct {
	Field        string
	SemanticType string
	Meaning      string
	Aliases      []string
}

var dimensionCatalog = []dimensionDefinition{
	{Field: "device_type", SemanticType: "device_category", Meaning: "Device category observed on the governed entrant event.", Aliases: []string{"device", "devices", "mobile", "platform"}},
	{Field: "os", SemanticType: "operating_system", Meaning: "Operating system observed on the governed entrant event.", Aliases: []string{"os", "operating system", "platform"}},
	{Field: "app_version", SemanticType: "client_version", Meaning: "Application version observed on the governed entrant event.", Aliases: []string{"app version", "version"}},
	{Field: "geoip_country_code", SemanticType: "event_location_country", Meaning: "Country inferred from event network location; it is not verified residence or nationality.", Aliases: []string{"geo", "geography", "country", "countries", "geoip"}},
	{Field: "city", SemanticType: "event_location_city", Meaning: "City observed with the entrant event; it is not verified residence, hometown, or travel destination.", Aliases: []string{"city", "cities", "geo city"}},
	{Field: "destination", SemanticType: "travel_destination", Meaning: "Visa or travel destination selected for the application; it is not customer origin.", Aliases: []string{"destination", "destinations", "travel destination"}},
	{Field: "channel", SemanticType: "interaction_channel", Meaning: "Observed acquisition, notification, or interaction channel for the feature event.", Aliases: []string{"channel", "channels"}},
	{Field: "saved_method_type", SemanticType: "payment_method_type", Meaning: "Saved payment method type observed for the feature flow.", Aliases: []string{"payment method", "saved method", "method type"}},
	{Field: "group_size", SemanticType: "traveller_group_size", Meaning: "Number of travellers represented by the group application.", Aliases: []string{"group size", "party size"}},
	{Field: "from_currency", SemanticType: "source_currency", Meaning: "Currency converted from in the observed quote or payment flow.", Aliases: []string{"source currency", "from currency", "currency pair", "currency pairs", "currencies"}},
	{Field: "to_currency", SemanticType: "target_currency", Meaning: "Currency converted to in the observed quote or payment flow.", Aliases: []string{"target currency", "to currency", "currency pair", "currency pairs", "currencies"}},
	{Field: "source_currency", SemanticType: "source_currency", Meaning: "Currency converted from in the observed quote or payment flow.", Aliases: []string{"source currency", "from currency"}},
	{Field: "target_currency", SemanticType: "target_currency", Meaning: "Currency converted to in the observed quote or payment flow.", Aliases: []string{"target currency", "to currency"}},
	{Field: "currency", SemanticType: "transaction_currency", Meaning: "Currency attached to the observed feature event.", Aliases: []string{"currency", "currencies"}},
}

func governedDimensionDefinitions(profile domain.EventProfile) []dimensionDefinition {
	dimensions := make([]dimensionDefinition, 0, len(dimensionCatalog))
	for _, definition := range dimensionCatalog {
		if hasField(profile, definition.Field) {
			dimensions = append(dimensions, definition)
		}
	}
	return dimensions
}

func governedDimensionNames(profile domain.EventProfile) []string {
	definitions := governedDimensionDefinitions(profile)
	dimensions := make([]string, 0, len(definitions))
	for _, definition := range definitions {
		dimensions = append(dimensions, definition.Field)
	}
	return dimensions
}

// GovernedDimensionNames exposes the semantic dimension contract to the
// independent context-evolution evaluator.
func GovernedDimensionNames(profile domain.EventProfile) []string {
	return governedDimensionNames(profile)
}

func dimensionDefinitionFor(field string) (dimensionDefinition, bool) {
	for _, definition := range dimensionCatalog {
		if definition.Field == field {
			return definition, true
		}
	}
	return dimensionDefinition{}, false
}

func requestedDimensions(question string, profile domain.EventProfile) []string {
	lower := " " + strings.ToLower(question) + " "
	requested := []string{}
	for _, definition := range governedDimensionDefinitions(profile) {
		for _, alias := range definition.Aliases {
			if strings.Contains(lower, " "+alias+" ") || strings.Contains(lower, " "+alias+"?") || strings.Contains(lower, " "+alias+",") {
				requested = append(requested, definition.Field)
				break
			}
		}
	}
	return requested
}

func dimensionLimitations(field string) []string {
	definition, ok := dimensionDefinitionFor(field)
	if !ok {
		return nil
	}
	return []string{definition.Meaning, "Segment differences are observational and may reflect eligibility, traffic mix, or collection coverage."}
}
