import 'package:equatable/equatable.dart';

/// Situação da tela de telemetria.
enum StatusTelemetria {
  /// Lendo os registros.
  carregando,

  /// Pronta; veja `TelemetriaState.total`.
  pronta,

  /// Abrindo o compartilhamento.
  exportando,

  /// Falha; veja `TelemetriaState.mensagem`.
  falha,
}

/// Estado de `/telemetria`.
class TelemetriaState extends Equatable {
  /// Cria o estado.
  const new({
    this.status = StatusTelemetria.carregando,
    this.total = 0,
    this.mensagem,
  });

  /// Situação.
  final StatusTelemetria status;

  /// Consultas registradas.
  final int total;

  /// Mensagem de falha.
  final String? mensagem;

  @override
  List<Object?> get props => [status, total, mensagem];
}
