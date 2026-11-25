import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';

/// Endereço do back-end em vigor: o salvo em ajustes ou, na falta dele, o
/// do `--dart-define`.
class ObterEnderecoBackend {
  /// Cria o caso de uso.
  const new(this._configuracao);

  final ConfiguracaoRepository _configuracao;

  /// Endereço em vigor, ou `null` se nenhum foi configurado.
  Future<String?> call() => _configuracao.enderecoBackend();
}
