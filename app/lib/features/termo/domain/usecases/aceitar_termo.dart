import 'package:app/core/error/failures.dart';
import 'package:app/features/termo/domain/repositories/termo_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Registra o aceite do termo com a data/hora atual.
class AceitarTermo {
  /// Cria o caso de uso; `agora` existe para tornar o relógio testável.
  const new(this._repositorio, {this._agora = DateTime.now});

  final TermoRepository _repositorio;
  final DateTime Function() _agora;

  /// Grava e devolve o instante do aceite.
  Future<Either<Failure, DateTime>> call() async {
    final quando = _agora();
    final gravado = await _repositorio.registrarAceite(quando);
    return gravado.map((_) => quando);
  }
}
