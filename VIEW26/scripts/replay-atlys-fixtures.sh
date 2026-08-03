#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ATLYS_DATASET_DIR:-}" ]]; then
  echo "Set ATLYS_DATASET_DIR to the Atlys folder containing specs/." >&2
  exit 1
fi

featurelens_url="${FEATURELENS_API_URL:-http://localhost:8080}"
use_existing_data="${FEATURELENS_USE_EXISTING_DATA:-true}"

for feature_dir in "${ATLYS_DATASET_DIR}"/specs/*; do
	case "$(basename "${feature_dir}")" in
		01_express_checkout) feature_name="Express Checkout"; schema_version=1 ;;
		02_group_family) feature_name="Group / Family"; schema_version=2 ;;
		03_status_sharing) feature_name="Status Sharing"; schema_version=2 ;;
		04_abandoned_checkout_recovery) feature_name="Abandoned Checkout Recovery"; schema_version=2 ;;
		05_instant_forex) feature_name="Instant Forex"; schema_version=2 ;;
		*) feature_name="$(basename "${feature_dir}" | sed -E 's/^[0-9]+_//; s/_/ /g')"; schema_version=1 ;;
	esac

	if [[ "${use_existing_data}" == "true" ]]; then
		payload="$(jq -n \
			--arg name "${feature_name}" \
			--argjson schema_version "${schema_version}" \
			--rawfile spec "${feature_dir}/spec.md" \
			'{name: $name, schema_version: $schema_version, spec_markdown: $spec, use_existing_data: true, role: "product_manager", auto_approve: true}')"
	else
		payload="$(jq -n \
			--arg name "${feature_name}" \
			--argjson schema_version "${schema_version}" \
			--rawfile spec "${feature_dir}/spec.md" \
			--rawfile events "${feature_dir}/events.ndjson" \
			'{name: $name, schema_version: $schema_version, spec_markdown: $spec, events_ndjson: $events, role: "product_manager", auto_approve: true}')"
	fi
	run_id="$(printf '%s' "${payload}" \
		| curl --fail --silent --show-error -H 'Content-Type: application/json' -d @- "${featurelens_url}/api/runs" \
		| jq -r '.id')"

  echo "Started ${feature_name}: ${run_id}"
  while true; do
    stage="$(curl --fail --silent --show-error "${featurelens_url}/api/runs/${run_id}" | jq -r '.stage')"
    if [[ "${stage}" == "completed" ]]; then
      curl --fail --silent --show-error "${featurelens_url}/api/runs/${run_id}" \
        | jq '{feature: .input.name, context: .context.version, evaluations: [.evaluations[] | {name, score, passed}]}'
      break
    fi
    if [[ "${stage}" == "failed" ]]; then
      curl --fail --silent --show-error "${featurelens_url}/api/runs/${run_id}" | jq '{stage, error}' >&2
      exit 1
    fi
    sleep 1
  done
done
