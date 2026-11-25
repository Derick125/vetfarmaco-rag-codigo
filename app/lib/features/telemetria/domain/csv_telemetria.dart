import 'package:app/features/telemetria/domain/registro_telemetria.dart';

/// Colunas do CSV, na ordem de saída.
const colunasCsv = [
  'consulta_id',
  'data',
  'modelo_versao',
  'thinking_level',
  'rede',
  'condicao_campanha',
  'desfecho',
  'nivel_confianca',
  'primeiro_evento_ms',
  'ttft_ms',
  'total_cliente_ms',
  'primeiro_token_servidor_ms',
  'primeiro_paragrafo_validado_servidor_ms',
  'total_servidor_ms',
  'custo_latencia_validacao_ms',
  'input_tokens',
  'output_tokens',
  'thought_tokens',
  'custo_usd',
  'chunks_recuperados',
  'paragrafos',
  'falha',
];

/// CSV (vírgula, ponto decimal, uma linha por consulta) para a análise de
/// P50/P90/P99 fora do app.
String gerarCsv(List<RegistroTelemetria> registros) {
  final linhas = [
    colunasCsv.join(','),
    for (final r in registros) _linha(r).map(_celula).join(','),
  ];
  return '${linhas.join('\n')}\n';
}

List<Object?> _linha(RegistroTelemetria r) => [
  r.consultaId,
  r.data.toUtc().toIso8601String(),
  r.modelo,
  r.thinkingLevel,
  r.rede,
  r.condicaoCampanha.rotulo,
  r.desfecho.rotulo,
  r.nivelConfianca,
  r.primeiroEventoMs,
  r.ttftMs,
  r.totalClienteMs,
  r.primeiroTokenServidorMs,
  r.primeiroParagrafoValidadoServidorMs,
  r.totalServidorMs,
  r.custoLatenciaValidacaoMs,
  r.inputTokens,
  r.outputTokens,
  r.thoughtTokens,
  r.custoUsd,
  r.chunks,
  r.paragrafos,
  r.falha,
];

String _celula(Object? v) {
  if (v == null) return '';
  final texto = v is double ? _decimal(v) : '$v';
  final precisaAspas = texto.contains(RegExp('[",\n\r]'));
  return precisaAspas ? '"${texto.replaceAll('"', '""')}"' : texto;
}

String _decimal(double v) {
  final t = v.toStringAsFixed(6).replaceFirst(RegExp(r'0+$'), '');
  return t.endsWith('.') ? t.substring(0, t.length - 1) : t;
}
