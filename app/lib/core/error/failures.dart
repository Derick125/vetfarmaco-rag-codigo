import 'package:equatable/equatable.dart';

/// Falha tipada que atravessa as camadas no lugar de exceções
/// (`docs/ARCHITECTURE.md` §4).
sealed class Failure extends Equatable {
  const new(this.mensagem);

  /// Mensagem em português, própria para exibir ao usuário.
  final String mensagem;

  @override
  List<Object?> get props => [mensagem];
}

/// Sem conectividade.
final class FalhaRede extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Tempo esgotado.
final class FalhaTempo extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Erro 5xx do servidor.
final class FalhaServidor extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Cota atingida (429).
final class FalhaCota extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Erro no armazenamento local (`hive_ce`).
final class FalhaCache extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Resposta fora do contrato.
final class FalhaContrato extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// Entrada do usuário inválida (ex.: endereço do back-end malformado).
final class FalhaValidacao extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}

/// `chunk_id` inexistente no conjunto recuperado: invalida a resposta inteira.
final class FalhaCitacao extends Failure {
  /// Cria a falha.
  const new(super.mensagem);
}
