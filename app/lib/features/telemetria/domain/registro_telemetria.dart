import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:equatable/equatable.dart';

/// Como a consulta terminou.
enum DesfechoConsulta {
  /// `fim` com evidência.
  concluida('concluida'),

  /// `fim` com `semEvidencia` (sucesso sem parágrafo validado).
  semEvidencia('sem_evidencia'),

  /// Erro do servidor, citação fantasma, contrato ou cota.
  falha('falha'),

  /// Queda de rede ou tempo esgotado depois de parágrafos recebidos.
  incompleta('incompleta'),

  /// Servida do cache, sem rede; fora das estatísticas de latência.
  cache('cache');

  new(this.rotulo);

  /// Valor gravado no CSV.
  final String rotulo;
}

/// Medições de uma consulta (`docs/CRITERIOS_DE_ACEITE.md`, OE5).
///
/// Os tempos ficam separados: o `ttftMs` do contrato (primeiro parágrafo
/// validado) não se mistura com o primeiro evento nem com o primeiro token.
class RegistroTelemetria extends Equatable {
  /// Cria o registro.
  const new({
    required this.consultaId,
    required this.data,
    required this.rede,
    required this.desfecho,
    required this.totalClienteMs,
    this.modelo,
    this.thinkingLevel,
    this.condicaoCampanha = CondicaoCampanha.naoInformada,
    this.nivelConfianca,
    this.primeiroEventoMs,
    this.ttftMs,
    this.primeiroTokenServidorMs,
    this.primeiroParagrafoValidadoServidorMs,
    this.totalServidorMs,
    this.inputTokens,
    this.outputTokens,
    this.thoughtTokens,
    this.custoUsd,
    this.chunks,
    this.paragrafos = 0,
    this.falha,
  });

  /// Identificador local da consulta.
  final String consultaId;

  /// Data/hora da coleta (TCC §4.7).
  final DateTime data;

  /// Versão do modelo (TCC §4.7): a do evento `fim` e, se a consulta falhou
  /// antes dele, a informada por `GET /health` no envio. `null` só se o
  /// back-end nunca respondeu.
  final String? modelo;

  /// Nível de raciocínio (`low` ou `high`) decidido pelo servidor: o do `fim`
  /// ou, se a consulta falhou antes dele, o do evento `recuperacao`. Em cache,
  /// o da resposta guardada. `null` se o servidor nunca o informou.
  final String? thinkingLevel;

  /// Condição de rede ao enviar (`wifi`, `mobile`…).
  final String rede;

  /// Condição de rede da campanha escolhida em Ajustes (Wi-Fi, 4G, 5G).
  final CondicaoCampanha condicaoCampanha;

  /// Desfecho.
  final DesfechoConsulta desfecho;

  /// Nível de confiança do `fim`.
  final String? nivelConfianca;

  /// Ms até o primeiro evento do stream (cliente).
  final int? primeiroEventoMs;

  /// Ms até o primeiro parágrafo validado (cliente): o TTFT do contrato.
  final int? ttftMs;

  /// Ms desde o envio até o fim (cliente).
  final int totalClienteMs;

  /// Primeiro token do modelo (servidor).
  final double? primeiroTokenServidorMs;

  /// Primeiro parágrafo validado (servidor).
  final double? primeiroParagrafoValidadoServidorMs;

  /// Total (servidor).
  final double? totalServidorMs;

  /// Tokens de entrada.
  final int? inputTokens;

  /// Tokens de saída.
  final int? outputTokens;

  /// Tokens de raciocínio (entram no custo, lado da saída).
  final int? thoughtTokens;

  /// Custo em dólares.
  final double? custoUsd;

  /// Trechos recuperados.
  final int? chunks;

  /// Parágrafos validados recebidos.
  final int paragrafos;

  /// Tipo da falha, quando houve.
  final String? falha;

  /// Custo de latência da validação: primeiro parágrafo validado menos
  /// primeiro token, no servidor. `null` se algum dos dois falta.
  double? get custoLatenciaValidacaoMs {
    final p = primeiroParagrafoValidadoServidorMs;
    final t = primeiroTokenServidorMs;
    return p == null || t == null ? null : p - t;
  }

  @override
  List<Object?> get props => [
    consultaId,
    data,
    modelo,
    thinkingLevel,
    rede,
    condicaoCampanha,
    desfecho,
    nivelConfianca,
    primeiroEventoMs,
    ttftMs,
    totalClienteMs,
    primeiroTokenServidorMs,
    primeiroParagrafoValidadoServidorMs,
    totalServidorMs,
    inputTokens,
    outputTokens,
    thoughtTokens,
    custoUsd,
    chunks,
    paragrafos,
    falha,
  ];
}
