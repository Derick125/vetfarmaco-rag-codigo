import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';

/// Condição de rede da campanha escolhida em Ajustes.
class ObterCondicaoCampanha {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final AjustesRepository _repositorio;

  /// Condição salva, ou `naoInformada`.
  Future<CondicaoCampanha> call() => _repositorio.condicaoCampanha();
}
