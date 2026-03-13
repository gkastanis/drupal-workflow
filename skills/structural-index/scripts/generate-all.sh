#!/bin/bash
# generate-all.sh - Orchestrator for structural index generation
# Runs all generators, writes .generated-at timestamp
# Usage: generate-all.sh [project-dir]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
STRUCTURAL_DIR="$PROJECT_DIR/docs/semantic/structural"

mkdir -p "$STRUCTURAL_DIR"

echo "=== STRUCTURAL INDEX GENERATOR ==="
echo "Project: $PROJECT_DIR"
echo "Output:  $STRUCTURAL_DIR"
echo ""

GENERATORS=(
    "generate-service-graph.sh"
    "generate-route-map.sh"
    "generate-hook-registry.sh"
    "generate-plugin-registry.sh"
    "generate-entity-map.sh"
    "generate-entity-schemas.sh"
    "generate-base-fields.sh"
    "generate-permission-registry.sh"
    "generate-method-index.sh"
)

ERRORS=0
for gen in "${GENERATORS[@]}"; do
    if [[ -x "$SCRIPT_DIR/$gen" ]]; then
        echo "Running $gen..."
        if "$SCRIPT_DIR/$gen" "$PROJECT_DIR"; then
            echo "  Done."
        else
            echo "  WARNING: $gen failed (exit $?)"
            ((ERRORS++)) || true
        fi
    else
        echo "  SKIP: $gen not found or not executable"
    fi
done

echo ""

# Generate cross-reference files (depend on structural/*.md)
for gen in "generate-dependency-graph.sh" "generate-feature-map.sh"; do
    if [[ -x "$SCRIPT_DIR/$gen" ]]; then
        echo "Running $gen..."
        if "$SCRIPT_DIR/$gen" "$PROJECT_DIR"; then
            echo "  Done."
        else
            echo "  WARNING: $gen failed (exit $?)"
            ((ERRORS++)) || true
        fi
    fi
done

# Write timestamp only on clean run
if [[ "$ERRORS" -eq 0 ]]; then
    date -Iseconds > "$STRUCTURAL_DIR/.generated-at"
else
    echo "WARNING: Skipping .generated-at update due to $ERRORS error(s)."
fi

echo ""
echo "=== GENERATION COMPLETE ==="
echo "Files generated in: $STRUCTURAL_DIR"
echo "Errors: $ERRORS"
ls -la "$STRUCTURAL_DIR"/*.md 2>/dev/null || echo "(no markdown files generated)"
exit $((ERRORS > 0 ? 1 : 0))
