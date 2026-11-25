#!/usr/bin/env bash
# Verifica o limiar de cobertura de domain/ e data/ (Quadro 1 do TCC,
# docs/FRONTEND_SPEC.md §19 e docs/PLANO_DE_FASES.md — Fase 0).
#
# Uso: check_domain_data_coverage.sh [caminho-do-lcov] [limiar-percentual]
set -euo pipefail

lcov_file="${1:-coverage/lcov.info}"
threshold="${2:-70}"

if [ ! -f "$lcov_file" ]; then
  echo "Arquivo de cobertura não encontrado: $lcov_file" >&2
  echo "Rode 'flutter test --coverage' antes." >&2
  exit 1
fi

awk -v threshold="$threshold" '
  /^SF:/ {
    file = substr($0, 4)
    gsub(/\\/, "/", file)
    relevant = (file ~ /\/domain\//) || (file ~ /\/data\//)
  }
  /^DA:/ {
    if (relevant) {
      split($0, parts, ",")
      linesFound++
      if ((parts[2] + 0) > 0) linesHit++
    }
  }
  END {
    if (linesFound == 0) {
      print "Nenhuma linha instrumentada em domain/ ou data/ — nada para medir." > "/dev/stderr"
      exit 1
    }
    pct = (linesHit / linesFound) * 100
    printf("Cobertura em domain/ e data/: %.2f%% (%d/%d linhas)\n", pct, linesHit, linesFound)
    if (pct < threshold - 1e-9) {
      printf("Abaixo do limiar de %s%% exigido (CLAUDE.md §3, Quadro 1 do TCC).\n", threshold) > "/dev/stderr"
      exit 1
    }
  }
' "$lcov_file"
