import 'package:app/core/error/failures.dart';
import 'package:fpdart/fpdart.dart';

/// Persistência do aceite do termo de uso clínico (`docs/FRONTEND_SPEC.md` §8).
abstract interface class TermoRepository {
  /// Data/hora do aceite, ou `null` se ainda não aceito.
  Future<Either<Failure, DateTime?>> aceitoEm();

  /// Grava o aceite.
  Future<Either<Failure, Unit>> registrarAceite(DateTime quando);
}
