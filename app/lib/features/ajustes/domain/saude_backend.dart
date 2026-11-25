import 'package:equatable/equatable.dart';

/// Resposta de `GET /health`.
class SaudeBackend extends Equatable {
  /// Cria a resposta.
  const new({this.modeloId});

  /// Identificador do modelo em uso no back-end, se configurado.
  final String? modeloId;

  @override
  List<Object?> get props => [modeloId];
}
